#!/bin/bash
echo "You will need to pip install requests and pex for this"
mkdir -p bin
pex -v -r requirements.txt dataplicity -o bin/dataplicity -m dataplicity
