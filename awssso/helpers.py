import json
import re
import subprocess
from urllib.parse import urlparse

import keyring
import requests
from inquirer.errors import ValidationError

SPINNER_MSGS = {
    'token_refresh': 'Refreshing token',
    'mfa_send': 'Sending MFA code'
}


class SecretsManager():
    def __init__(self, username, url):
        self._username = username
        self._base_service_name = f'awssso.{urlparse(url).netloc}'

    def get(self, stype, default=None):
        return keyring.get_password(
            f'{self._base_service_name}.{stype}',
            self._username
        ) or default

    def set(self, stype, password):
        return keyring.set_password(
            f'{self._base_service_name}.{stype}',
            self._username,
            password
        )


class CredentialsHelper():
    CNAMES = {
        'AccessKeyId': {
            'awscli': 'aws_access_key_id',
            'env': 'AWS_ACCESS_KEY_ID',
            'console': 'sessionId'
        },
        'SecretAccessKey': {
            'awscli': 'aws_secret_access_key',
            'env': 'AWS_SECRET_ACCESS_KEY',
            'console': 'sessionKey'
        },
        'SessionToken': {
            'awscli': 'aws_session_token',
            'env': 'AWS_SESSION_TOKEN',
            'console': 'sessionToken'
        }
    }

    def __init__(self, credentials):
        self._credentials = credentials

    def configure_cli(self, profile):
        for _ in self._credentials:
            if _ in CredentialsHelper.CNAMES:
                subprocess.run([
                    'aws', 'configure',
                    '--profile', profile,
                    'set', CredentialsHelper.CNAMES[_]['awscli'], self._credentials[_]
                ])

    def configure_export(self, profile=None):
        exports = []
        for _ in self._credentials:
            if _ in CredentialsHelper.CNAMES:
                export = f'export {CredentialsHelper.CNAMES[_]["env"]}={self._credentials[_]}'
                exports.append(export)
        return '\n'.join(exports)

    def configure_json(self):
        export = {
            **self._credentials,
            **{
                'Version': 1,
                'Expiration': self._credentials['Expiration'].isoformat()
            }
        }
        return json.dumps(export)

    def console_signin(self, duration):
        session = {}
        for _ in self._credentials:
            if _ in CredentialsHelper.CNAMES:
                session.update({
                    CredentialsHelper.CNAMES[_]['console']: self._credentials[_]
                })

        params = {
            'Action': 'getSigninToken',
            'Session': json.dumps(session),
            'SessionDuration': duration
        }
        response = requests.get('https://signin.aws.amazon.com/federation', params=params)

        login_request = requests.Request(
            'GET',
            'https://signin.aws.amazon.com/federation',
            params={
                'Action': 'login',
                'Destination': 'https://console.aws.amazon.com/',
                'SigninToken': response.json()['SigninToken']
            }
        ).prepare()

        return login_request.url


def config_override(config, section, args, keep=['url', 'region', 'username', 'aws_profile']):
    if section not in config:
        config[section] = {}
    params = config[section]

    for arg in vars(args):
        value = getattr(args, arg)
        if (not keep) or (arg in keep and value is not None):
            params[arg] = value
    return params


def validate_url(answers, url):
    rx = r'^https://[\S-]+\.awsapps\.com/start/$'
    if re.match(rx, url) is None:
        raise ValidationError('', reason=f'URL must match {rx}')
    return True


def validate_empty(answers, s):
    if not s:
        raise ValidationError('', reason='Must not be empty')
    return True
