import argparse
import os
import subprocess
from time import sleep

import keyring
from halo import Halo
from PyInquirer import print_json, prompt

from awssso import __version__
from awssso.config import Configuration
from awssso.ssodriver import SSODriver


def configure(args):
    configuration = Configuration()
    config = configuration.read_section(args.profile)
    keyring_service_name = f'awssso-{args.profile}'

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

    cookies_file = f'{configuration.config_dir()}/{args.profile}-cookies.pkl'
    with SSODriver(headless=args.no_headless, cookies_file=cookies_file) as driver:
        with Halo(text='Signing in'):
            driver.get(answers['url'])
            driver.login(answers['username'], answers['password'])

        with Halo(text='Checking for MFA'):
            mfa = driver.check_mfa()
        if mfa:
            mfacode = prompt({
                'type': 'input',
                'name': 'mfacode',
                'message': 'MFA',
            })['mfacode']
            driver.send_mfa(mfa, mfacode)

        app_id = args.app_id or config.get('app_id')
        if not app_id:
            with Halo(text='Listing applications'):
                app_ids = driver.get_applications()
            app_id = prompt({
                'type': 'list',
                'name': 'app_id',
                'message': 'Application ID',
                'choices': app_ids
            })['app_id']
        answers['app_id'] = app_id

        with Halo(text=f'Listing AWS Accounts for {answers["app_id"]}'):
            accounts = driver.get_accounts(answers['app_id'])

        instance_name = prompt({
            'type': 'list',
            'name': 'aws_account',
            'message': 'AWS Account',
            'choices': [_ for _ in accounts]
        })['aws_account']
        instance_id = accounts[instance_name]

        with Halo(text=f'Listing AWS Profiles for {instance_name} ({instance_id})'):
            profiles = driver.get_profiles(instance_id)

        profile_name = prompt({
            'type': 'list',
            'name': 'aws_profile',
            'message': 'AWS Profile',
            'choices': [_ for _ in profiles]
        })['aws_profile']
        profile_id = profiles[profile_name]

        keyring.set_password(keyring_service_name, answers['username'], answers.pop('password'))
        updated_config = {}
        updated_config.update(answers)
        updated_config.update({
            'instance_id': instance_id,
            'profile_id': profile_id
        })

        configuration.write_section(args.profile, updated_config)


def login(args):
    configuration = Configuration()
    config = configuration.read_section(args.profile)
    keyring_service_name = f'awssso-{args.profile}'

    url = config.get('url')
    username = config.get('username')
    password = keyring.get_password(keyring_service_name, username)
    app_id = config.get('app_id')
    instance_id = config.get('instance_id')
    profile_id = config.get('profile_id')

    cookies_file = f'{configuration.config_dir()}/{args.profile}-cookies.pkl'
    with SSODriver(headless=args.no_headless, cookies_file=cookies_file) as driver:
        driver.get(url)
        driver.login(username, password)

        mfa = driver.check_mfa()
        if mfa:
            mfacode = prompt({
                'type': 'input',
                'name': 'mfacode',
                'message': 'MFA',
            })['mfacode']
            driver.send_mfa(mfa, mfacode)

        credentials = driver.get_credentials(app_id, instance_id, profile_id)

    for _ in credentials:
        subprocess.run([
            "aws", "configure",
            "--profile", config.get('aws_profile'),
            "set", _, credentials[_]
        ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('--no-headless', action='store_false', default=True)
    subparsers = parser.add_subparsers()

    configure_parser = subparsers.add_parser('configure')
    configure_parser.add_argument('--profile', default='default')
    configure_parser.add_argument('--url')
    configure_parser.add_argument('--username')
    configure_parser.add_argument('--app-id')
    configure_parser.add_argument('--aws-profile')
    configure_parser.set_defaults(func=configure)

    login_parser = subparsers.add_parser('login')
    login_parser.add_argument('--profile', default='default')
    login_parser.set_defaults(func=login)

    args = parser.parse_args()
    args.func(args)
