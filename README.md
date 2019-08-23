# aws-sso

[![PyPi Version](https://img.shields.io/pypi/v/awssso.svg?style=flat)](https://pypi.python.org/pypi/awssso/)

This package provides a command line interface to get AWS credentials with [AWS SSO](https://aws.amazon.com/single-sign-on/).

The aws-cli package works on Python versions:
  - 3.7.x and greater

#### Attention!

This package relies on [Selenium](https://www.seleniumhq.org/) and Google Chrome to work.
Therefore, you need [Google Chrome](https://www.google.com/chrome/) and [ChromeDriver](https://chromedriver.chromium.org/) to be installed.

## Installation

```shell
pip install awssso
```

### Dependencies

#### macOS

```shell
brew cask install chromedriver
```

## Getting Started

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

```
$ awssso login -e
export AWS_ACCESS_KEY_ID=ACCESS_KEY_ID
export AWS_SECRET_ACCESS_KEY=SECRET_ACCESS_KEY
export AWS_SESSION_TOKEN=SESSION_TOKEN
```

This will echo `export` commands to stdout ; can be used like this `$(awssso login -e)`
