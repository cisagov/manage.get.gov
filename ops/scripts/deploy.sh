#!/bin/sh

# Check for app name

SANDBOXNAME=${1:-}

if [ -z "$SANDBOXNAME" ]; then
    echo "ERROR: Sandbox name is missing"
    exit 1
fi


# Compile and collect static assets
../ops/scripts/build.sh

# Collect git info
if [[ "$SANDBOXNAME" == "staging" ]]; then
    TAG=$(git describe --tags --abbrev=0)
else
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
fi

COMMIT=$(git rev-parse HEAD)

# Deploy to sandbox 
cf target -o cisa-dotgov -s $1

if [ "$SANDBOXNAME" = "staging" ]; then   
    cf push getgov-$1 -f  ../ops/manifests/manifest-$1.yaml --var GIT_TAG="$TAG" --var GIT_COMMIT_SHA="$COMMIT" --strategy rolling 
else
    cf push getgov-$1 -f  ../ops/manifests/manifest-$1.yaml --var GIT_BRANCH="$BRANCH" --var GIT_COMMIT_SHA="$COMMIT" --strategy rolling 
fi

# migrations need to be run manually. Developers can use this command
#cf run-task getgov-SANDBOXNAME --command 'python manage.py migrate' --name migrate