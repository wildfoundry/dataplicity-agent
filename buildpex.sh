#!/bin/bash
pip install pex -U
mkdir -p bin
pex -r requirements.txt dataplicity -o bin/dataplicity -c dataplicity
