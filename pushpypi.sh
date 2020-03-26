#!/bin/bash
sudo rm dist/*
sudo python setup.py sdist bdist_wheel
twine upload dist/*
