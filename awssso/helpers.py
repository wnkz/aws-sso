import json
import re
import subprocess
from datetime import date, datetime, timezone
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
    def __init__(self, credentials):
        self.credentials = credentials

    @property
    def credentials(self):
        return self._credentials

    @property
    def access_key_id(self):
        return self.credentials['AccessKeyId']

    @property
    def secret_access_key(self):
        return self.credentials['SecretAccessKey']

    @property
    def session_token(self):
        return self.credentials['SessionToken']

    @property
    def json(self):
        return json.dumps(self.credentials, default=json_serial)

    @property
    def cli(self):
        return {
            'aws_access_key_id': self.access_key_id,
            'aws_secret_access_key': self.secret_access_key,
            'aws_session_token': self.session_token
        }

    @property
    def env(self):
        return {
            'AWS_ACCESS_KEY_ID': self.access_key_id,
            'AWS_SECRET_ACCESS_KEY': self.secret_access_key,
            'AWS_SESSION_TOKEN': self.session_token
        }

    @property
    def console(self):
        return {
            'sessionId': self.access_key_id,
            'sessionKey': self.secret_access_key,
            'sessionToken': self.session_token
        }

    @credentials.setter
    def credentials(self, credentials):
        if isinstance(credentials['Expiration'], str):
            credentials['Expiration'] = datetime.fromisoformat(credentials['Expiration'])
        self._credentials = credentials

    @property
    def expiration(self):
        return self.credentials['Expiration']

    @property
    def expired(self):
        return self.expiration < datetime.now(timezone.utc)

    def to_cli_cmds(self, profile):
        cmds = []
        for key, value in self.cli.items():
            cmds.append([
                'aws', 'configure',
                '--profile', profile,
                'set', key, value
            ])
        return cmds

    def to_exports(self):
        return [f'export {key}={value}' for key, value in self.env.items()]

    def to_json(self):
        return json.dumps({
            **self.credentials,
            'Version': 1
        }, default=json_serial)

    def to_console_url(self, duration=None):
        params = {
            'Action': 'getSigninToken',
            'Session': json.dumps(self.console),
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


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError('Type %s not serializable' % type(obj))
