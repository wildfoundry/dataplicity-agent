#!/bin/bash

pyenv=$(which pyenv)
interpreters=(2.7 3.7 3.9 3.10)

read -p "Build dataplicity agent v$(python dataplicity/_version.py) from PyPi? " -n 1 -r
echo
if [[ ! "$REPLY" =~ ^[Yy]$ ]]
then
    exit 1
fi

# check if pyenv is installed:
if [ ! -e ~/.pyenv/ ]
then
    echo "Make sure you have pyenv installed"
    exit 1
fi

pyenvRoot=$("$pyenv" root)

buildParams=""
for version in ${interpreters[@]}; do
    fullVersion=$(pyenv install --list | grep "^  $version" | tail -1 | xargs)
    echo "${version} => ${fullVersion}"
    pyenv install -s $fullVersion
    buildParams="$buildParams--python=$pyenvRoot/versions/$fullVersion/bin/python "
done

mkdir -p bin
rm -f bin/dataplicity
rm -rf .build
python3 -m venv .build
source .build/bin/activate
pip -q install pex==2.1.112 subprocess32
echo building ./bin/dataplicity
echo "pex dataplicity==$(python dataplicity/_version.py) --pre --python-shebang='#!/usr/bin/env python' -r requirements.txt -o bin/dataplicity -m dataplicity.app:main $buildParams"
pex dataplicity==$(python dataplicity/_version.py) --pre --python-shebang='#!/usr/bin/env python' -r requirements.txt -o bin/dataplicity -m dataplicity.app:main $buildParams
deactivate
echo built dataplicity agent v$(./bin/dataplicity version)
