# aws-sso

[![PyPi Version](https://img.shields.io/pypi/v/aws-sso.svg?style=flat)](https://pypi.python.org/pypi/awssso/)

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
? URL  https://d-0123456789.awsapps.com/start#/
? Username  me@example.com
? Password  ***************
? AWS CLI Profile  Master-Admin
? MFA  000000
? Application ID  app-0000000000000000
? AWS Account  000000000000 (Master)
? AWS Profile  AWSAdministratorAccess
```

This will create a configuration file in `~/.awssso/config`.

### Get credentials

```
$ awssso login
```

This will get the credentials for the `profile` as defined in the configuration file
and use `aws-cli` to set those credentials to the correct AWS Profile.
