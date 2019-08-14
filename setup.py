#!/usr/bin/env python
import codecs
import os.path
import re
import sys

from setuptools import find_packages, setup

from awssso import __version__

requires = [
    'awscli',
    'selenium',
    'keyring',
    'PyInquirer',
    'halo'
]

setup_options = dict(
    name='awssso',
    version=__version__,
    description='Command Line tool for AWS SSO Credentials',
    long_description=open('README.rst').read(),
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
    license="Apache License 2.0",
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
