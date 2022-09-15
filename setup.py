# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

with open('requirements.txt') as f:
	install_requires = f.read().strip().split('\n')

# get version from __version__ variable in hampden/__init__.py
from hampden import __version__ as version

setup(
	name='hampden',
	version=version,
	description='ERPnext implementation for Hampden',
	author='ahmadragheb',
	author_email='Ahmedragheb75@gmail.com',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
