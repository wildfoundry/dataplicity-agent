#!/bin/bash

read -p "Build dataplicity agent v$(python dataplicity/_version.py) from PyPi? " -n 1 -r
echo
if [[ ! "$REPLY" =~ ^[Yy]$ ]]
then
    exit 1
fi

mkdir -p bin
rm -f bin/dataplicity
rm -rf .build
virtualenv -qq .build -p python3
source .build/bin/activate
pip -q install pex==2.1.21 subprocess32
echo building ./bin/dataplicity
pex dataplicity==$(python dataplicity/_version.py) --pre --python-shebang="#!/usr/bin/env python" --python=$(which python2) --python=$(which python3) -r requirements.txt -o bin/dataplicity -m dataplicity.app:main
deactivate
echo built dataplicity agent v$(./bin/dataplicity version)
