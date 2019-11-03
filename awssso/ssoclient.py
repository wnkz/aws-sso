import logging

import requests
from requests.exceptions import HTTPError

LOG = logging.getLogger(__name__)

class SSOClientError(Exception):
    """Base class for SSOClient exceptions."""

class SSOClientHttpError(HTTPError):
    """Base class for SSOClient HTTP exceptions."""


class SSOClient():
    def __init__(self, token=None, region='eu-west-1'):
        self._session = requests.Session()
        self.token = token
        self.region = region

    @property
    def token(self):
        return self._token

    @token.setter
    def token(self, value):
        self._token = value
        self._session.headers.update({
            'x-amz-sso_bearer_token': self._token
        })

    @property
    def region(self):
        return self._region

    @region.setter
    def region(self, value):
        self._region = value

    def whoami(self):
        r = self._session.get(f'https://portal.sso.{self._region}.amazonaws.com/token/whoAmI')
        return r.json()

    def get_instances(self):
        try:
            r = self._session.get(f'https://portal.sso.{self._region}.amazonaws.com/instance/appinstances')
            r.raise_for_status()
            return [i for i in r.json()['result'] if i['applicationName'] == 'AWS Account']
        except HTTPError as http_err:
            raise SSOClientHttpError(http_err)
        except Exception as e:
            raise SSOClientError(e)

    def get_profiles(self, instance_id):
        try:
            r = self._session.get(f'https://portal.sso.{self._region}.amazonaws.com/instance/appinstance/{instance_id}/profiles')
            r.raise_for_status()
            return r.json()['result']
        except HTTPError as http_err:
            raise SSOClientHttpError(http_err)
        except Exception as e:
            raise SSOClientError(e)

    def get_saml_payload(self, instance_id, profile_id):
        for profile in self.get_profiles(instance_id):
            if profile['id'] == profile_id:
                url = profile['url']

        try:
            r = self._session.get(url)
            r.raise_for_status()
            return r.json()['encodedResponse']
        except HTTPError as http_err:
            raise SSOClientHttpError(http_err)
        except Exception as e:
            raise SSOClientError(e)
