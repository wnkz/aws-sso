#!/usr/bin/env python
from setuptools import find_packages, setup

requires = [
    'awscli',
    'boto3',
    'halo',
    'keyring',
    'inquirer',
    'secretstorage; platform_system == "Linux"',
    'selenium',
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
        'Development Status :: 3 - Alpha',

        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',

        'Natural Language :: English',

        'License :: OSI Approved :: Apache Software License',

        'Programming Language :: Python :: 3.7'
    ]
)

setup(**setup_options)
