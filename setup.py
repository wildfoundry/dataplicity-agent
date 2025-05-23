#!/usr/bin/env python

from setuptools import setup, find_packages
import sys

classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Programming Language :: Python",
]

# http://bit.ly/2alyerp
with open("dataplicity/_version.py") as f:
    exec(f.read())

with open("README.md") as f:
    long_desc = f.read()

# Only require enum34 for Python versions without built-in enum support
install_requires = ["six==1.10.0", "lomond==0.3.3"]
if sys.version_info < (3, 4):
    install_requires.append("enum34==1.1.6")

setup(
    name="dataplicity",
    version=__version__,
    description="Platform for connected devices",
    long_description=long_desc,
    author="WildFoundry",
    author_email="support@dataplicity.com",
    url="https://www.dataplicity.com",
    platforms=["any"],
    packages=find_packages(),
    classifiers=classifiers,
    entry_points={"console_scripts": ["dataplicity = dataplicity.app:main"]},
    install_requires=install_requires,
    zip_safe=True,
)
