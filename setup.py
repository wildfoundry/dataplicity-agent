#!/usr/bin/env python

from setuptools import setup, find_packages
import sys

classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Programming Language :: Python",
    "Programming Language :: Python :: 2.7",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

# http://bit.ly/2alyerp
with open("dataplicity/_version.py") as f:
    exec(f.read())

with open("README.md") as f:
    long_desc = f.read()

install_requires = [
    "lomond==0.3.3",
    "distro==1.6.0",
]

# Version-specific dependencies
if sys.version_info < (3, 4):
    install_requires.append("six==1.10.0")
    install_requires.append("enum34==1.1.6")
else:
    install_requires.append("six==1.16.0")

setup(
    name="dataplicity",
    version=__version__,
    description="Platform for connected devices",
    long_description=long_desc,
    long_description_content_type="text/markdown",
    author="WildFoundry",
    author_email="support@dataplicity.com",
    url="https://www.dataplicity.com",
    platforms=["any"],
    packages=find_packages(),
    classifiers=classifiers,
    entry_points={"console_scripts": ["dataplicity = dataplicity.app:main"]},
    install_requires=install_requires,
    python_requires='>=2.7',
    zip_safe=True,
)
