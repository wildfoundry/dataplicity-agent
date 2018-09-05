#!/bin/bash

read -p "Build dataplicity agent from PyPi? " -n 1 -r
echo
if [[ ! "$REPLY" =~ ^[Yy]$ ]]
then
    exit 1
fi

mkdir -p bin
rm bin/dataplicity
virtualenv -qq .build -p Python2.7
source .build/bin/activate
pip -q install pex==1.2.13
echo building ./bin/dataplicity
pex dataplicity==0.4.32a1 --pre -r requirements.txt -o bin/dataplicity -m dataplicity.app:main
deactivate
echo built dataplicity agent v`./bin/dataplicity version`
