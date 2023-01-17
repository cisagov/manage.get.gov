#!/bin/sh

# Compile and collect static assets
../ops/scripts/build.sh

# Deploy to sandbox 
cf target -o cisa-getgov-prototyping -s $1
cf push getgov-$1 -f ../ops/manifests/manifest-$1.yaml

# migrations need to be run manually. Developers can use this command
#cf run-task getgov-SANDBOXNAME --command 'python manage.py migrate' --name migrate