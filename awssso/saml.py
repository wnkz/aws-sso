import xml.etree.ElementTree as ET
from base64 import b64decode

import boto3
from botocore.exceptions import ClientError


class Error(Exception):
    """Base class for SAMLHelper exceptions."""

    def __init__(self, msg=''):
        self.message = msg
        Exception.__init__(self, msg)

    def __repr__(self):
        return self.message

    __str__ = __repr__


class BotoClientError(Error):
    """Raised when boto call failed."""

    def __init__(self, response):
        Error.__init__(self, response['Error']['Message'])
        self.request_id = response['ResponseMetadata']['RequestId']
        self.args = (response, )


class AssumeRoleValidationError(BotoClientError):
    """Raised when SAML assertion validation failed."""

    pass


class SAMLHelper():
    NS = {
        'a': 'urn:oasis:names:tc:SAML:2.0:assertion'
    }

    XPATH = {
        'roles': ".//a:Assertion/a:AttributeStatement/a:Attribute[@Name='https://aws.amazon.com/SAML/Attributes/Role']/a:AttributeValue",
        'duration': ".//a:Assertion/a:AttributeStatement/a:Attribute[@Name='https://aws.amazon.com/SAML/Attributes/SessionDuration']/a:AttributeValue"
    }

    def __init__(self, encoded_payload):
        # Calling AssumeRoleWithSAML does not require the use of AWS security credentials.
        # The identity of the caller is validated by using keys in the metadata document that is uploaded for the SAML provider entity for your identity provider.
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sts.html#STS.Client.assume_role_with_saml
        self._sts = boto3.client('sts', aws_access_key_id='', aws_secret_access_key='', aws_session_token='')
        self._root = ET.fromstring(b64decode(encoded_payload))
        self._role_arn, self._principal_arn = self._get_roles()
        self._duration = self._get_duration()
        self._payload = encoded_payload

    @property
    def duration(self):
        return self._duration

    def _get_roles(self):
        e = self._root.find(SAMLHelper.XPATH['roles'], SAMLHelper.NS)
        return tuple(e.text.split(','))

    def _get_duration(self):
        e = self._root.find(SAMLHelper.XPATH['duration'], SAMLHelper.NS)
        return int(e.text)

    def assume_role(self, duration=None):
        duration = duration or self._duration
        try:
            return self._sts.assume_role_with_saml(
                RoleArn=self._role_arn,
                PrincipalArn=self._principal_arn,
                SAMLAssertion=self._payload,
                DurationSeconds=duration
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ValidationError':
                raise AssumeRoleValidationError(e.response)
            else:
                raise BotoClientError(e.response)
