import argparse
import json
import logging
import os
import subprocess
import sys
import webbrowser
from time import time
import signal

import inquirer
from halo import Halo

from awssso import __version__
from awssso.config import Configuration
from awssso.helpers import (SPINNER_MSGS, CredentialsHelper, SecretsManager,
                            config_override, validate_empty, validate_url)
from awssso.saml import AssumeRoleValidationError, BotoClientError, SAMLHelper
from awssso.ssoclient import SSOClient, SSOClientError, SSOClientHttpError
from awssso.ssodriver import AlertMessage, MFACodeNeeded, SSODriver
from requests.exceptions import HTTPError

logging.basicConfig(format='%(asctime)s - %(threadName)s - %(name)s - %(levelname)s - %(message)s')
LOG = logging.getLogger()


class DurationAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if values < 900 or values > 43200:
            parser.error(f'argument {option_string}: value must be between 900 and 43200')
        setattr(namespace, self.dest, values)


def main():
    return CLIDriver().main()


class AWSSSOManager():
    def __init__(self, username, url, config_dir, **kwargs):
        default_region = os.environ.get('AWSSSO_REGION')
        default_region = default_region or os.environ.get('AWS_DEFAULT_REGION', 'eu-west-1')

        self._username = username
        self._url = url
        self._config_dir = config_dir
        self._secrets = SecretsManager(self._username, self._url)
        self._sso_client = SSOClient(self.token, region=kwargs.get('region', default_region))
        self._headless = kwargs.get('headless', True)
        self._spinner = Halo(enabled=kwargs.get('spinner', True), stream=sys.stderr)
        self.instance_id = kwargs.get('instance_id')
        self.profile_id = kwargs.get('profile_id')

        self._credentials = CredentialsHelper()

    @property
    def password(self):
        return self._secrets.get('credentials')

    @password.setter
    def password(self, value):
        if self.password != value:
            self._secrets.set('credentials', value)

    @property
    def token(self):
        return self._secrets.get('authn-token')

    @token.setter
    def token(self, value):
        if isinstance(value, tuple):
            token = value[0]
            self.token_expiry_date = value[1]
        else:
            token = value
        self._secrets.set('authn-token', token)
        self._sso_client.token = token

    @property
    def token_expiry_date(self):
        return int(self._secrets.get('authn-expiry-date', '0'))

    @token_expiry_date.setter
    def token_expiry_date(self, value):
        self._secrets.set('authn-expiry-date', str(value))

    @property
    def token_expired(self):
        return time() > self.token_expiry_date

    @property
    def instance_id(self):
        return self._instance_id

    @instance_id.setter
    def instance_id(self, value):
        self._instance_id = value

    @property
    def profile_id(self):
        return self._profile_id

    @profile_id.setter
    def profile_id(self, value):
        self._profile_id = value

    @property
    def sso_client(self):
        return self._sso_client

    @property
    def credentials(self):
        if not self._credentials.credentials:
            self._credentials.credentials = self._secrets.get(f'{self.instance_id}.{self.profile_id}.credentials', {})
        return self._credentials

    @credentials.setter
    def credentials(self, value):
        self._credentials.credentials = value
        self._secrets.set(f'{self.instance_id}.{self.profile_id}.credentials', self._credentials.json)

    def get_credentials(self, duration=None, renew=False, renew_token=False):
        if self.credentials.expired or renew or renew_token:
            self.get_token(renew_token)
            self.credentials = SAMLHelper(
                self.sso_client.get_saml_payload(self.instance_id, self.profile_id)
            ).assume_role(duration)['Credentials']
        return self

    def get_token(self, renew=False):
        if (self.token_expired) or (renew):
            self.token = self.__refresh_token()
        return self

    def __refresh_token(self):
        url = self._url
        username = self._username
        headless = self._headless
        config_dir = self._config_dir
        spinner = self._spinner
        try:
            spinner.start(SPINNER_MSGS['token_refresh'])
            driver = SSODriver(url, username, headless=headless, cookie_dir=config_dir)
            try:
                return driver.refresh_token(username, self.password)
            except MFACodeNeeded as e:
                spinner.stop()
                mfacode = inquirer.text(message='MFA Code')
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


class CLICommand():
    def __init__(self, name, subparsers):
        self.parser = subparsers.add_parser(name, parents=[self._create_parser()])
        self.parser.set_defaults(command=self)
        self.cfg = Configuration()

    def _create_parser(self):
        default_profile = 'default'
        default_aws_profile = os.environ.get('AWS_PROFILE')
        default_aws_profile = default_aws_profile or os.environ.get('AWS_DEFAULT_PROFILE')

        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('-p', '--profile', default=default_profile, help=f'AWS SSO Profile (default: {default_profile})')
        parser.add_argument('-a', '--aws-profile', default=default_aws_profile, help='AWS CLI Profile (default: AWS_PROFILE, fallback: same as --profile)')
        parser.add_argument('-f', '--force-refresh', action='store_true', default=False, help='force token refresh')
        return parser

    def __call__(self, args, remaining):
        raise NotImplementedError


class ConfigureCommand(CLICommand):
    def __init__(self, subparsers):
        super().__init__('configure', subparsers)

        self.parser.add_argument('--url')
        self.parser.add_argument('--username')

    def __call__(self, args, remaining):
        LOG.debug(f'{self.__class__.__name__}.__call__({args}, {remaining})')
        params = self.cfg.read().arguments_override(args.profile, args, True)

        inquirer.prompt([
            inquirer.Text('url', message='URL', default=params.get('url', ''), validate=validate_url),
            inquirer.Text('aws_profile', message='AWS CLI profile', default=params.get('aws_profile', args.profile), validate=validate_empty),
            inquirer.Text('region', message='AWS SSO region', default=params.get('region'), validate=validate_empty),
            inquirer.Text('username', message='Username', default=params.get('username', ''), validate=validate_empty)
        ], answers=params, raise_keyboard_interrupt=True)

        mngr = AWSSSOManager(
            params.get('username'),
            params.get('url'),
            self.cfg.config_dir,
            region=params['region']
        )

        mngr.password = inquirer.password(message='Password', default=mngr.password, validate=validate_empty)
        mngr.get_token()

        inquirer.prompt([
            inquirer.List(
                'instance_id',
                message='AWS Account',
                choices=[(_['name'], _['id']) for _ in mngr.sso_client.get_instances()]
            )
        ], answers=params, raise_keyboard_interrupt=True)

        inquirer.prompt([
            inquirer.List(
                'profile_id',
                message='AWS Profile',
                choices=[(_['name'], _['id']) for _ in mngr.sso_client.get_profiles(params['instance_id'])]
            )
        ], answers=params, raise_keyboard_interrupt=True)

        self.cfg.save()


class LoginCommand(CLICommand):
    def __init__(self, subparsers):
        super().__init__('login', subparsers)

        self.parser.add_argument('-r', '--renew', action='store_true', default=False, help='ignore cached credentials and renew them')
        self.parser.add_argument('-d', '--duration', action=DurationAction, type=int, help='duration (seconds) of the role session (default: from role, minimum: 900, maximum: 43200)')
        self.parser.add_argument('-i', '--interactive', action='store_true', default=False, help='interactively choose AWS account and role')

        self.parser_ag_output = self.parser.add_argument_group('output')
        self.parser_ag_output_meg = self.parser_ag_output.add_mutually_exclusive_group()
        self.parser_ag_output_meg.add_argument('-o', '--output', choices=['json', 'export', 'console'])
        self.parser_ag_output_meg.add_argument('-e', '--export', action='store_true', default=False, help='output credentials as environment variables')
        # https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sourcing-external.html
        self.parser_ag_output_meg.add_argument('-j', '--json', action='store_true', default=False, help='output credentials in JSON format')
        self.parser_ag_output_meg.add_argument('-c', '--console', action='store_true', default=False, help='output AWS Console Sign In url')

        self.parser_ag_console = self.parser.add_argument_group('console (ignored unless used with --console)')
        self.parser_ag_console.add_argument('-b', '--browser', action='store_true', default=False, help='open web browser with AWS Console Sign In url (ignored unless used with --console)')
        # https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_enable-console-custom-url.html
        self.parser_ag_console.add_argument('--session-duration', action=DurationAction, type=int, help='duration (seconds) of the console session')

    def __call__(self, args, remaining):
        LOG.debug(f'{self.__class__.__name__}.__call__({args}, {remaining})')
        try:
            params = self.cfg.read().arguments_override(args.profile, args)
        except KeyError:
            raise RuntimeError(f'profile {args.profile} does not exist, use "awssso configure -p {args.profile}" to create it')

        mngr = AWSSSOManager(
            params.get('username'),
            params.get('url'),
            self.cfg.config_dir,
            region=params['region']
        )

        if args.interactive:
            mngr.get_token(args.force_refresh)
            setattr(args, 'force_refresh', False)
            inquirer.prompt([
                inquirer.List(
                    'instance_id',
                    message='AWS Account',
                    choices=[(_['name'], _['id']) for _ in mngr.sso_client.get_instances()]
                )
            ], answers=params, raise_keyboard_interrupt=True)

            inquirer.prompt([
                inquirer.List(
                    'profile_id',
                    message='AWS Profile',
                    choices=[(_['name'], _['id']) for _ in mngr.sso_client.get_profiles(params['instance_id'])]
                )
            ], answers=params, raise_keyboard_interrupt=True)

        mngr.instance_id = params['instance_id']
        mngr.profile_id = params['profile_id']

        credentials = mngr.get_credentials(
            args.duration,
            args.renew,
            args.force_refresh
        ).credentials

        if args.output == 'json' or args.json:
            print(credentials.to_json())
        elif args.output == 'export' or args.export:
            print('\n'.join(credentials.to_exports()))
        elif args.output == 'console' or args.console:
            signin_url = credentials.to_console_url(args.session_duration)
            print(signin_url)
            if args.browser:
                webbrowser.open_new_tab(signin_url)
        else:
            for cmd in credentials.to_cli_cmds(params['aws_profile']):
                LOG.debug(f'running command: {cmd}')
                subprocess.run(cmd)


class ExecCommand(CLICommand):
    def __init__(self, subparsers):
        super().__init__('exec', subparsers)

        self.parser.add_argument('-r', '--renew', action='store_true', default=False, help='ignore cached credentials and renew them')
        self.parser.add_argument('-d', '--duration', action=DurationAction, type=int, help='duration (seconds) of the role session (default: from role, minimum: 900, maximum: 43200)')
        self.parser.add_argument('cmd', nargs=argparse.REMAINDER)

    def __call__(self, args, remaining):
        LOG.debug(f'{self.__class__.__name__}.__call__({args})')
        try:
            params = self.cfg.read().arguments_override(args.profile, args)
        except KeyError:
            raise RuntimeError(f'profile {args.profile} does not exist, use "awssso configure -p {args.profile}" to create it')

        mngr = AWSSSOManager(
            params.get('username'),
            params.get('url'),
            self.cfg.config_dir,
            region=params['region'],
            instance_id=params['instance_id'],
            profile_id=params['profile_id']
        )

        credentials = mngr.get_credentials(args.duration).credentials
        environment = os.environ.copy()
        environment.update(credentials.env)

        try:
            cmd = ' '.join(args.cmd)
            LOG.debug(f'running command: {cmd}')
            return subprocess.run(cmd, env=environment, shell=True, check=True).returncode
        except subprocess.CalledProcessError as e:
            return e.returncode


class CLIDriver():
    def __init__(self):
        self.parser, self.subparsers = self._create_parser()
        self.commands = {
            'configure': ConfigureCommand(self.subparsers),
            'login': LoginCommand(self.subparsers),
            'exec': ExecCommand(self.subparsers)
        }

    def _create_parser(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--version', action='version', version=__version__)
        parser.add_argument('--log', help='log level (e.g. info, debug, trace, ...)')
        parser.add_argument('--region', help='AWS SSO region (default: AWSSSO_REGION, AWS_DEFAULT_REGION, eu-west-1)')
        parser.add_argument('--no-headless', dest='headless', action='store_false', default=True, help='show web browser')
        parser.add_argument('--no-spinner', dest='spinner', action='store_false', default=True, help='disable all spinners')
        subparsers = parser.add_subparsers(title='commands', required=True)
        return (parser, subparsers)

    def main(self):
        parsed_args, remaining = self.parser.parse_known_args()

        if parsed_args.log:
            log_level = getattr(logging, parsed_args.log.upper(), None)
            if not isinstance(log_level, int):
                print(f'Invalid log level: {parsed_args.log}', file=sys.stderr)
                return 1
            LOG.setLevel(log_level)

        try:
            return parsed_args.command(parsed_args, remaining)
        except KeyboardInterrupt:
            return 128 + signal.SIGINT
        except (RuntimeError, HTTPError) as e:
            print(e, file=sys.stderr)
            return 1
        except Exception:
            LOG.debug('Exception caught in main()', exc_info=True)
            return 255
