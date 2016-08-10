#!/bin/bash
pip install requests
pip install pex -U
mkdir -p bin
pex -v -r requirements.txt dataplicity -o bin/dataplicity -c dataplicity
