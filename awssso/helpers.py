import re
import subprocess
import xml.etree.ElementTree as ET
from base64 import b64decode
from urllib.parse import urlparse

import boto3
import keyring
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
            'env': 'AWS_ACCESS_KEY_ID'
        },
        'SecretAccessKey': {
            'awscli': 'aws_secret_access_key',
            'env': 'AWS_SECRET_ACCESS_KEY'
        },
        'SessionToken': {
            'awscli': 'aws_session_token',
            'env': 'AWS_SESSION_TOKEN'
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

class SAMLHelper():
    NS = {
        'a': 'urn:oasis:names:tc:SAML:2.0:assertion'
    }

    XPATH = {
        'roles': ".//a:Assertion/a:AttributeStatement/a:Attribute[@Name='https://aws.amazon.com/SAML/Attributes/Role']/a:AttributeValue",
        'duration': ".//a:Assertion/a:AttributeStatement/a:Attribute[@Name='https://aws.amazon.com/SAML/Attributes/SessionDuration']/a:AttributeValue"
    }

    def __init__(self, encoded_payload):
        self._sts = boto3.client('sts')
        self._root = ET.fromstring(b64decode(encoded_payload))
        self._role_arn, self._principal_arn = self._get_roles()
        self._duration = self._get_duration()
        self._payload = encoded_payload

    def _get_roles(self):
        e = self._root.find(SAMLHelper.XPATH['roles'], SAMLHelper.NS)
        return tuple(e.text.split(','))

    def _get_duration(self):
        e = self._root.find(SAMLHelper.XPATH['duration'], SAMLHelper.NS)
        return int(e.text)

    def assume_role(self, duration=None):
        duration = duration or self._duration
        return self._sts.assume_role_with_saml(
            RoleArn=self._role_arn,
            PrincipalArn=self._principal_arn,
            SAMLAssertion=self._payload,
            DurationSeconds=duration
        )


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
