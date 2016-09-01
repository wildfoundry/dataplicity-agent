#!/bin/bash
echo "You will need to pip install requests and pex for this"
mkdir -p bin
pex -r agent_requirements.txt -o bin/dataplicity -m dataplicity.app:main
