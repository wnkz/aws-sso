import argparse
import json
import os
import subprocess
import sys
import traceback
import webbrowser
from time import time

import inquirer
from halo import Halo

from awssso import __version__
from awssso.config import Configuration
from awssso.helpers import (SPINNER_MSGS, CredentialsHelper, SecretsManager,
                            config_override, validate_empty, validate_url)
from awssso.nonterminal import NonInteractiveRender, Bland
from awssso.saml import AssumeRoleValidationError, BotoClientError, SAMLHelper
from awssso.ssoclient import SSOClient
from awssso.ssodriver import AlertMessage, MFACodeNeeded, SSODriver


def __refresh_token(url, username, password, config_dir, headless=True, spinner=True, render=None):
    spinner = Halo(enabled=spinner)
    try:
        driver = SSODriver(url, username, headless=headless, cookie_dir=config_dir)
    except Exception as e:
        sys.stderr.write(e.msg+'\n')
        raise e
    try:
        spinner.start(SPINNER_MSGS['token_refresh'])
        try:
            return driver.refresh_token(username, password)
        except MFACodeNeeded as e:
            spinner.stop()
            mfacode = inquirer.text(message='MFA Code', render=render)
            spinner.start(SPINNER_MSGS['mfa_send'])
            driver.send_mfa(e.mfa_form, mfacode)
            spinner.start(SPINNER_MSGS['token_refresh'])
            return driver.get_token()
        except AlertMessage as e:
            sys.exit(e)
        finally:
            spinner.stop()
    except KeyboardInterrupt as e:
        spinner.stop()
        raise e
    finally:
        driver.close()


def __get_or_refresh_token(url, username, password, secrets, config_dir, force_refresh=False, headless=True, spinner=True, render=None):
    token = secrets.get('authn-token')
    stored_password = secrets.get('credentials')
    expiry_date = int(secrets.get('authn-expiry-date', '0'))
    if (force_refresh) or (not token) or (time() > expiry_date) or (stored_password != password):
        res = __refresh_token(url, username, password, config_dir, headless, spinner, render=render)
        token, expiry_date = res
        if stored_password != password:
            secrets.set('credentials', password)
        secrets.set('authn-token', token)
        secrets.set('authn-expiry-date', str(expiry_date))
    return token

def configure(args):
    profile = args.profile
    cfg = Configuration()
    params = config_override(cfg.config, profile, args)

    render = None
    if bool(os.getenv('AWSSSO_NO_CONSOLE', False)):
        render = NonInteractiveRender(theme=Bland())

    try:
        inquirer.prompt([
            inquirer.Text('url', message='URL', default=params.get('url', ''), validate=validate_url, show_default=bool(os.getenv('AWSSSO_NO_CONSOLE', False))),
            inquirer.Text('aws_profile', message='AWS CLI profile', default=params.get('aws_profile', profile), validate=validate_empty, show_default=bool(os.getenv('AWSSSO_NO_CONSOLE', False))),
            inquirer.Text('username', message='Username', default=params.get('username', ''), validate=validate_empty, show_default=bool(os.getenv('AWSSSO_NO_CONSOLE', False)))
        ], answers=params, raise_keyboard_interrupt=True, render=render)
        secrets = SecretsManager(params.get('username'), params.get('url'))
        password = inquirer.password(message='Password', default=secrets.get('credentials', os.getenv('AWSSSO_PASSWORD', '')), validate=validate_empty, render=render)

        token = __get_or_refresh_token(
            params['url'], params['username'], password,
            secrets, cfg.configdir, args.force_refresh, args.headless, args.spinner,
            render=render
        )
        sso = SSOClient(token, params['region'])

        instances = sso.get_instances()
        inquirer.prompt([
            inquirer.List(
                'instance_id',
                message='AWS Account',
                choices=[(_['name'], _['id']) for _ in instances]
            )
        ], answers=params, raise_keyboard_interrupt=True)

        profiles = sso.get_profiles(params['instance_id'])
        inquirer.prompt([
            inquirer.List(
                'profile_id',
                message='AWS Profile',
                choices=[(_['name'], _['id']) for _ in profiles]
            )
        ], answers=params, raise_keyboard_interrupt=True)

        cfg.save()
    except KeyboardInterrupt:
        sys.exit(1)


def login(args):
    profile = args.profile
    cfg = Configuration()

    if profile not in cfg.config:
        sys.exit(f'profile {profile} does not exist, use "awssso configure -p {profile}" to create it')

    render = None
    if bool(os.getenv('AWSSSO_NO_CONSOLE', False)):
        render = NonInteractiveRender(theme=Bland())

    params = config_override(cfg.config, profile, args)
    aws_profile = params.get('aws_profile', profile)
    secrets = SecretsManager(params.get('username'), params.get('url'))
    password = secrets.get('credentials')

    if not password:
        sys.exit(f'Cannot get password from secrets, run "awssso configure -p {profile}"')

    try:
        token = __get_or_refresh_token(
            params['url'], params['username'], password,
            secrets, cfg.configdir, args.force_refresh, args.headless, args.spinner, render=render
        )
        sso = SSOClient(token, params['region'])

        if args.interactive:
            instances = sso.get_instances()
            inquirer.prompt([
                inquirer.List(
                    'instance_id',
                    message='AWS Account',
                    choices=[(_['name'], _['id']) for _ in instances]
                )
            ], answers=params, raise_keyboard_interrupt=True)

            profiles = sso.get_profiles(params['instance_id'])
            inquirer.prompt([
                inquirer.List(
                    'profile_id',
                    message='AWS Profile',
                    choices=[(_['name'], _['id']) for _ in profiles]
                )
            ], answers=params, raise_keyboard_interrupt=True)

        cache_key = f"{params['instance_id']}.{params['profile_id']}.credentials"
        cached_credentials = secrets.get(cache_key)

        if cached_credentials:
            credentials = CredentialsHelper(json.loads(cached_credentials))

        if not cached_credentials or credentials.expired or args.renew:
            payload = sso.get_saml_payload(params['instance_id'], params['profile_id'])
            saml = SAMLHelper(payload)
            credentials = CredentialsHelper(saml.assume_role(args.duration)['Credentials'])
            secrets.set(cache_key, credentials.json)

        if args.export:
            print('\n'.join(credentials.to_exports()))
        elif args.json:
            print(credentials.to_json())
        elif args.console:
            signin_url = credentials.to_console_url(args.duration)
            print(signin_url)
            if args.browser:
                webbrowser.open_new_tab(signin_url)
        else:
            for cmd in credentials.to_cli_cmds(aws_profile):
                subprocess.run(cmd)
    except (AssumeRoleValidationError, BotoClientError) as e:
        sys.exit(f'{e} (request id: {e.request_id})')
    except KeyboardInterrupt:
        sys.exit(1)


class DurationAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if values < 900:
            parser.error(f'argument {option_string}: minimum value is 900')
        setattr(namespace, self.dest, values)


def main():
    default_region = os.environ.get('AWSSSO_REGION')
    default_region = default_region or os.environ.get('AWS_DEFAULT_REGION', 'eu-west-1')

    default_profile = 'default'
    default_aws_profile = os.environ.get('AWS_PROFILE')
    default_aws_profile = default_aws_profile or os.environ.get('AWS_DEFAULT_PROFILE')

    parser = argparse.ArgumentParser()
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('--region', default=default_region, help='AWS SSO region (default: AWSSSO_REGION, AWS_DEFAULT_REGION, eu-west-1)')
    parser.add_argument('--no-headless', dest='headless', action='store_false', default=True, help='show web browser')
    parser.add_argument('--no-spinner', dest='spinner', action='store_false', default=True, help='disable all spinners')
    subparsers = parser.add_subparsers(title='subcommands')

    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument('-p', '--profile', default=default_profile, help=f'AWS SSO Profile (default: {default_profile})')
    parent_parser.add_argument('-a', '--aws-profile', default=default_aws_profile, help='AWS CLI Profile (default: AWS_PROFILE, fallback: same as --profile)')
    parent_parser.add_argument('-f', '--force-refresh', action='store_true', default=False, help='force token refresh')

    configure_parser = subparsers.add_parser('configure', parents=[parent_parser])
    configure_parser.add_argument('--url')
    configure_parser.add_argument('--username')
    configure_parser.set_defaults(func=configure)

    login_parser = subparsers.add_parser('login', parents=[parent_parser])
    login_parser.add_argument('-d', '--duration', action=DurationAction, type=int, help='duration (seconds) of the role session (default/maximum: from SAML payload, minimum: 900)')
    login_parser_group = login_parser.add_mutually_exclusive_group()
    login_parser_group.add_argument('-e', '--export', action='store_true', default=False, help='output credentials as environment variables')
    login_parser_group.add_argument('-j', '--json', action='store_true', default=False,
                                    help='output credentials in JSON format (see https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sourcing-external.html)')
    login_parser_group.add_argument('-c', '--console', action='store_true', default=False, help='output AWS Console Sign In url')
    login_parser.add_argument('-b', '--browser', action='store_true', default=False, help='open web browser with AWS Console Sign In url')
    login_parser.add_argument('-i', '--interactive', action='store_true', default=False, help='interactively choose AWS account and role')
    login_parser.add_argument('-r', '--renew', action='store_true', default=False, help='ignore cached credentials and renew them')
    login_parser.set_defaults(func=login)

    args = parser.parse_args()

    try:
        func = args.func
        if callable(func):
            func(args)
    except AttributeError as ae:
        traceback.print_exception(AttributeError, ae, ae.__traceback__)
        parser.print_help(sys.stderr)
