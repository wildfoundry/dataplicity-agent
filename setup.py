#!/usr/bin/env python

from setuptools import setup, find_packages

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
    install_requires=["enum34==1.1.6", "six==1.10.0", "lomond==0.3.3"],
    zip_safe=True,
)
