import pickle

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class SSODriver(object):
    def __init__(self, headless=True, cookies_file=None):
        self._cookies_file = cookies_file
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        self._driver = webdriver.Chrome(chrome_options=chrome_options)
        self._driver.implicitly_wait(5)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        if self._cookies_file:
            pickle.dump(self._driver.get_cookies(), open(self._cookies_file, 'wb'))
        self._driver.quit()

    def _find_element_by_id(self, element_id, driver=None, timeout=5):
        driver = driver or self._driver
        return WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((By.ID, element_id))
        )

    def _click_element_by_id(self, element_id, driver=None, timeout=5):
        element = self._find_element_by_id(element_id, driver, timeout)
        element.click()
        return element

    def get(self, url):
        self._driver.get(url)
        if self._cookies_file:
            try:
                cookies = pickle.load(open(self._cookies_file, 'rb'))
                for cookie in cookies:
                    if 'expiry' in cookie:
                        del cookie['expiry']
                    self._driver.add_cookie(cookie)
            except FileNotFoundError:
                pass
        return self._driver

    def login(self, username, password):
        el_username = self._find_element_by_id('wdc_username')
        el_password = self._find_element_by_id('wdc_password')
        el_signin = self._find_element_by_id('wdc_login_button')

        el_username.clear()
        el_username.send_keys(username)
        el_password.clear()
        el_password.send_keys(password)
        el_signin.click()

    def check_mfa(self):
        try:
            wait = WebDriverWait(self._driver, 1)
            mfa = wait.until(EC.presence_of_element_located((By.ID, 'mfa_form')))
            return mfa
        except TimeoutException as e:
            pass
        return False

    def send_mfa(self, mfa_form, mfacode, trusted_device=True):
        el_mfacode = self._find_element_by_id('wdc_mfacode')
        el_mfacheckbox = self._find_element_by_id('wdc_mfacheckbox')
        el_signin = self._find_element_by_id('wdc_login_button')

        el_mfacode.clear()
        el_mfacode.send_keys(mfacode)
        if trusted_device:
            el_mfacheckbox.click()
        el_signin.click()

    def get_applications(self):
        application_list = self._driver.find_element_by_tag_name('portal-application-list')
        application_ids = []
        for application in application_list.find_elements_by_tag_name('portal-application'):
            application_name = application.find_element_by_css_selector('div.title').get_attribute('title')
            if 'AWS Account' in application_name:
                application_ids.append(application.get_attribute('id'))
        return application_ids

    def get_accounts(self, app_id):
        self._click_element_by_id(app_id)

        portal_list = self._driver.find_element_by_xpath('/html/body/app/portal-ui/div/portal-dashboard/portal-application-list/sso-expander/portal-instance-list')
        accounts = {}
        for portal_instance in portal_list.find_elements_by_tag_name('portal-instance'):
            accounts[portal_instance.text] = portal_instance.get_attribute('id')
        return accounts

    def get_profiles(self, instance_id):
        account = self._driver.find_element_by_id(instance_id)
        account.click()
        profile_list = account.find_element_by_tag_name('portal-profile-list')
        profiles = {}
        for profile in profile_list.find_elements_by_tag_name('portal-profile'):
            profile_name = WebDriverWait(profile, 10).until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'span.profileName')))
            profiles[profile_name.text] = profile.get_attribute('id')
        return profiles

    def get_credentials(self, app_id, instance_id, profile_id):
        self._click_element_by_id(app_id)
        account = self._click_element_by_id(instance_id)
        profile = self._find_element_by_id(profile_id, driver=account)
        creds_button = self._click_element_by_id('temp-credentials-button')
        sso_modal = self._driver.find_element_by_tag_name('sso-modal')
        access_key_id = sso_modal.find_element_by_id('accessKeyId')
        secret_access_key = sso_modal.find_element_by_id('secretAccessKey')
        session_token = sso_modal.find_element_by_id('sessionToken')

        return {
            'aws_access_key_id': access_key_id.get_attribute('value'),
            'aws_secret_access_key': secret_access_key.get_attribute('value'),
            'aws_session_token': session_token.get_attribute('value')
        }
