#!/bin/sh

# Compile and collect static assets
../ops/scripts/build.sh

# Deploy to unstable 
cf target -o cisa-getgov-prototyping -s unstable
cf push getgov-unstable -f ../ops/manifests/manifest-unstable.yaml

cf run-task getgov-unstable --command 'python manage.py migrate' --name migrate
