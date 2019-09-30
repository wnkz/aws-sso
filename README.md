# aws-sso

[![GitHub Actions status](https://github.com/wnkz/aws-sso/workflows/Python%20package/badge.svg)](https://github.com/wnkz/aws-sso)
[![GitHub Actions status](https://github.com/wnkz/aws-sso/workflows/Upload%20Python%20Package/badge.svg)](https://github.com/wnkz/aws-sso)
[![PyPi Version](https://img.shields.io/pypi/v/awssso.svg?style=flat)](https://pypi.python.org/pypi/awssso/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/awssso)
![PyPI - Downloads](https://img.shields.io/pypi/dm/awssso)


This package provides a command line interface to get AWS credentials with [AWS SSO](https://aws.amazon.com/single-sign-on/).

The aws-cli package works on Python versions:
  - 3.7.x and greater

#### Attention!

This package relies on [Selenium](https://www.seleniumhq.org/) and Google Chrome to work.
Therefore, you need [Google Chrome](https://www.google.com/chrome/) and [ChromeDriver](https://chromedriver.chromium.org/) to be installed.

This is being developped and tested on macOS, if you encounter problems on other platforms, please open an issue.

### Dependencies

#### macOS

```shell
brew cask install chromedriver
```

#### Linux

```
¯\_(ツ)_/¯
```

## Installation

```shell
pip install awssso
```

## Getting Started

### Help

For each command you can get help with `--help` flag.

```
usage: awssso configure [-h] [-p PROFILE] [-a AWS_PROFILE] [-f] [--url URL]
                        [--username USERNAME]

optional arguments:
  -h, --help            show this help message and exit
  -p PROFILE, --profile PROFILE
                        AWS SSO Profile (default: default)
  -a AWS_PROFILE, --aws-profile AWS_PROFILE
                        AWS CLI Profile (default: AWS_PROFILE, fallback: same
                        as --profile)
  -f, --force-refresh   force token refresh
  --url URL
  --username USERNAME
```

### Configure a profile

```
$ awssso configure
[?] URL: https://d-0123456789.awsapps.com/start/
[?] AWS CLI profile: my-awssso-profile
[?] Username: me@example.com
[?] Password: **************
[?] MFA Code: 042042
[?] AWS Account: 000000000000 (Master)
   111111111111 (Log archive)
   222222222222 (Audit)
 > 000000000000 (Master)

[?] AWS Profile: AWSAdministratorAccess
   AWSServiceCatalogEndUserAccess
 > AWSAdministratorAccess
```

This will create a configuration file in `~/.awssso/config`.

### Get credentials

```
$ awssso login
```

This will get the credentials for the `profile` as defined in the configuration file
and use `aws-cli` to set those credentials to the correct AWS Profile.

---

```
$ awssso login -e
export AWS_ACCESS_KEY_ID=ACCESS_KEY_ID
export AWS_SECRET_ACCESS_KEY=SECRET_ACCESS_KEY
export AWS_SESSION_TOKEN=SESSION_TOKEN
```

This will echo `export` commands to stdout ; can be used like this `$(awssso login -e)`

---

```
$ awssso login -c
https://signin.aws.amazon.com/federation?Action=login&Destination=https%3A%2F%2Fconsole.aws.amazon.com%2F&SigninToken=TOKEN
```

This will generate a Sign In URL to the AWS Console ; URL will open in a new tab if used with `--browser`.

---

You can also use this tool as a [credential_process](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sourcing-external.html) for awscli. To do so, configure your awscli configuration file like so:

```
[profile my-sso-profile]
credential_process = awssso login -p my-awssso-profile --json
```

And then simply use awscli normally:

```
$ aws --profile my-sso-profile s3 ls
```

## Base concepts

aws-sso has its own configuration file (`~/.awssso/config`).  
Each section in this file corresponds to an AWS SSO profile. Those profiles are different from AWS profiles.

When using the `login` command, it'll set credentials for the configured AWS Profile by invoking `aws configure`.

Inside `~/.awssso/` are also stored cookie files for each pair of username / url. This allows not prompting for MFA code at each login.

Secrets are stored using [keyring](https://pypi.org/project/keyring/) so for example on macOS they are stored in Keychain.  
For each username / url aws-sso stores three secrets:

* password
* authn-token
* authn-expiry-date

aws-sso doesn't make new login attempts until authn-token is expired.  
aws-sso also stores credentials using keyring to avoid making too many STS calls.

## Releases

The release notes for AWS SSO can be found [here](CHANGELOG.md).

## Known issues

Known issues can be found [here](KNOWNISSUES.md).
