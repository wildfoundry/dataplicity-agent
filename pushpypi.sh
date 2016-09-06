#!/bin/bash
git tag -a v`dataplicity version` -m "auto tagged"
sudo python setup.py sdist bdist_wheel upload
