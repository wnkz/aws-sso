import requests

class SSOClient():
    def __init__(self, token, region='eu-west-1'):
        self._token = token
        self._region = region
        self._s = requests.Session()
        self._s.headers.update({
            'x-amz-sso_bearer_token': self._token
        })

    def whoami(self):
        r = self._s.get(f'https://portal.sso.{self._region}.amazonaws.com/token/whoAmI')
        return r.json()

    def get_instances(self):
        r = self._s.get(f'https://portal.sso.{self._region}.amazonaws.com/instance/appinstances')
        return [i for i in r.json()['result'] if i['applicationName'] == 'AWS Account']

    def get_profiles(self, instance_id):
        r = self._s.get(f'https://portal.sso.{self._region}.amazonaws.com/instance/appinstance/{instance_id}/profiles')
        return r.json()['result']

    def get_saml_payload(self, instance_id, profile_id):
        for profile in self.get_profiles(instance_id):
            if profile['id'] == profile_id:
                url = profile['url']
        r = self._s.get(url)
        return r.json()['encodedResponse']
