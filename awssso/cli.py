import argparse
import os
import subprocess

import keyring
from halo import Halo
from PyInquirer import print_json, prompt

from awssso import __version__
from awssso.config import Configuration
from awssso.ssodriver import SSODriver

SPINNER_MSGS = {
    'launch_browser': 'Starting web browser',
    'url_get': 'Loading URL',
    'sign_in': 'Signing in',
    'mfa_check': 'Checking for MFA',
    'mfa_needed': 'MFA code needed',
    'mfa_send': 'Sending MFA code',
    'ls_apps': 'Listing applications',
    'ls_aws_accts': 'Listing AWS Accounts for',
    'ls_aws_pf': 'Listing AWS Profiles for',
    'pwd_save': 'Saving password',
    'cfg_save': 'Saving configuration',
    'cfg_success': 'Successfully configured profile',
    'creds_get': 'Getting credentials',
    'creds_set': 'Setting credentials',
    'creds_success': 'Successfully set credentials'
}


def configure(args):
    configuration = Configuration()
    config = configuration.read_section(args.profile)
    keyring_service_name = f'awssso-{args.profile}'
    cookies_file = f'{configuration.config_dir()}/{args.profile}-cookies.pkl'
    spinner = Halo(enabled=args.no_spinner)

    questions = [
        {
            'type': 'input',
            'name': 'url',
            'message': 'URL',
            'default': args.url or config.get('url', '')
        },
        {
            'type': 'input',
            'name': 'username',
            'message': 'Username',
            'default': args.username or config.get('username', '')
        },
        {
            'type': 'password',
            'name': 'password',
            'message': 'Password',
            'default': keyring.get_password(keyring_service_name, args.username) or ''
        },
        {
            'type': 'input',
            'name': 'aws_profile',
            'message': 'AWS CLI Profile',
            'default': args.aws_profile or config.get('aws_profile', args.profile)
        }
    ]

    answers = prompt(questions)

    try:
        spinner.start(SPINNER_MSGS['launch_browser'])
        driver = SSODriver(headless=args.no_headless, cookies_file=cookies_file)

        spinner.start(SPINNER_MSGS['url_get'])
        driver.get(answers['url'])

        spinner.start(SPINNER_MSGS['sign_in'])
        driver.login(answers['username'], answers['password'])

        spinner.start(SPINNER_MSGS['mfa_check'])
        mfa = driver.check_mfa()

        if mfa:
            spinner.info(SPINNER_MSGS['mfa_needed'])
            mfacode = prompt({
                'type': 'input',
                'name': 'mfacode',
                'message': 'MFA',
            })['mfacode']
            spinner.start(SPINNER_MSGS['mfa_send'])
            driver.send_mfa(mfa, mfacode)

        default_app_id = args.app_id or config.get('app_id')
        spinner.start(SPINNER_MSGS['ls_apps'])
        app_ids = driver.get_applications()
        spinner.stop()
        app_id = prompt({
            'type': 'list',
            'name': 'app_id',
            'message': 'Application ID',
            'choices': app_ids,
            'default': default_app_id or 0
        })['app_id']

        answers['app_id'] = app_id
        spinner.start(f'{SPINNER_MSGS["ls_aws_accts"]} {answers["app_id"]}')
        accounts = driver.get_accounts(answers['app_id'])
        spinner.stop()

        instance_name = prompt({
            'type': 'list',
            'name': 'aws_account',
            'message': 'AWS Account',
            'choices': [_ for _ in accounts]
        })['aws_account']
        instance_id = accounts[instance_name]

        spinner.start(f'{SPINNER_MSGS["ls_aws_pf"]} {instance_name} ({instance_id})')
        profiles = driver.get_profiles(instance_id)
        spinner.stop()

        profile_name = prompt({
            'type': 'list',
            'name': 'aws_profile',
            'message': 'AWS Profile',
            'choices': [_ for _ in profiles]
        })['aws_profile']
        profile_id = profiles[profile_name]

        spinner.start(SPINNER_MSGS['pwd_save'])
        keyring.set_password(keyring_service_name, answers['username'], answers.pop('password'))

        updated_config = {}
        updated_config.update(answers)
        updated_config.update({
            'instance_id': instance_id,
            'profile_id': profile_id
        })

        spinner.start(SPINNER_MSGS['cfg_save'])
        configuration.write_section(args.profile, updated_config)

        spinner.succeed(f'{SPINNER_MSGS["cfg_success"]} {args.profile}')
    except (KeyboardInterrupt, SystemExit):
        spinner.stop()
    finally:
        driver.close()


def login(args):
    configuration = Configuration()
    config = configuration.read_section(args.profile)
    keyring_service_name = f'awssso-{args.profile}'
    cookies_file = f'{configuration.config_dir()}/{args.profile}-cookies.pkl'
    spinner = Halo(enabled=args.no_spinner)

    url = config.get('url')
    username = config.get('username')
    password = keyring.get_password(keyring_service_name, username)
    app_id = config.get('app_id')
    instance_id = config.get('instance_id')
    profile_id = config.get('profile_id')

    try:
        spinner.start(SPINNER_MSGS['launch_browser'])
        driver = SSODriver(headless=args.no_headless, cookies_file=cookies_file)

        spinner.start(SPINNER_MSGS['url_get'])
        driver.get(url)

        spinner.start(SPINNER_MSGS['sign_in'])
        driver.login(username, password)

        spinner.start(SPINNER_MSGS['mfa_check'])
        mfa = driver.check_mfa()
        if mfa:
            spinner.info(SPINNER_MSGS['mfa_needed'])
            mfacode = prompt({
                'type': 'input',
                'name': 'mfacode',
                'message': 'MFA',
            })['mfacode']
            spinner.start(SPINNER_MSGS['mfa_send'])
            driver.send_mfa(mfa, mfacode)

        spinner.start(SPINNER_MSGS['creds_get'])
        credentials = driver.get_credentials(app_id, instance_id, profile_id)

        spinner.start(SPINNER_MSGS['creds_set'])
        for _ in credentials:
            subprocess.run([
                'aws', 'configure',
                '--profile', args.aws_profile or config.get('aws_profile'),
                'set', _, credentials[_]
            ])

        spinner.succeed(SPINNER_MSGS['creds_success'])
    except (KeyboardInterrupt, SystemExit):
        spinner.stop()
    finally:
        driver.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('--no-headless', action='store_false', default=True, help='show web browser')
    parser.add_argument('--no-spinner', action='store_false', default=True, help='disable all spinners')
    subparsers = parser.add_subparsers()

    configure_parser = subparsers.add_parser('configure')
    configure_parser.add_argument('--profile', default='default', help='AWS SSO Profile (default: default)')
    configure_parser.add_argument('--url')
    configure_parser.add_argument('--username')
    configure_parser.add_argument('--app-id')
    configure_parser.add_argument('--aws-profile', help='AWS CLI Profile (default: same as --profile)')
    configure_parser.set_defaults(func=configure)

    login_parser = subparsers.add_parser('login')
    login_parser.add_argument('--profile', default='default')
    login_parser.add_argument('--aws-profile', help='override configured AWS CLI Profile')
    login_parser.set_defaults(func=login)

    args = parser.parse_args()
    args.func(args)
