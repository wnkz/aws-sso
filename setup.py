#!/usr/bin/env python
from setuptools import find_packages, setup

requires = [
    'awscli>=1.16.10,<2.0.0',
    'boto3>=1.9.0,<2.0.0',
    'halo',
    'inquirer>=2.6.0,<3.0.0',
    'keyring>=19.0.0,<20.0.0',
    'requests',
    'secretstorage; platform_system == "Linux"',
    'selenium>=3.14.0,<4.0.0',
]

with open('README.md', 'r') as fh:
    long_description = fh.read()

setup_options = dict(
    name='awssso',
    use_scm_version=True,
    description='Command Line tool for AWS SSO Credentials',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='wnkz',
    author_email='wnkz@users.noreply.github.com',
    url='http://github.com/wnkz/aws-sso',
    entry_points={
        'console_scripts': [
            'awssso=awssso.cli:main'
        ],
    },
    packages=find_packages(exclude=['tests*']),
    install_requires=requires,
    license='Apache License 2.0',
    classifiers=[
        'Development Status :: 5 - Production/Stable',

        'Environment :: Console',

        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',

        'Natural Language :: English',

        'License :: OSI Approved :: Apache Software License',

        'Operating System :: MacOS',
        'Operating System :: POSIX',

        'Programming Language :: Python :: 3.7'
    ],
    keywords=['aws', 'sso', 'cloud', 'cli', 'credentials']
)

setup(**setup_options)
