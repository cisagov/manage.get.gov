#!/bin/sh
# Running locally,
# Assumptions: 
# Already logged into the cloud.gov cli 
# The branch name follows our branch naming conventions
# Versioning info can be found at url: /health
# Notes: 
# Script restages app at the end to update changes

set -euo pipefail

if [[ -n "${GITHUB_ACTIONS:-}" && $GITHUB_ACTIONS = true ]]; then
    echo "Running in Github Actions"
    IS_CI=true
else
    echo "Running locally"
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    COMMIT=$(git rev-parse HEAD)
    ENVIRONMENT=${BRANCH%%/*}
    IS_CI=false
fi

# Get the tags
TAG=$(git tag --points-at HEAD)

if [ $IS_CI = true ]; then
    echo "Installing CF CLI ...."
    wget -q -O - https://packages.cloudfoundry.org/debian/cli.cloudfoundry.org.key | sudo gpg --dearmor -o /usr/share/keyrings/cli.cloudfoundry.org.gpg
    echo "deb [signed-by=/usr/share/keyrings/cli.cloudfoundry.org.gpg] https://packages.cloudfoundry.org/debian stable main" | sudo tee /etc/apt/sources.list.d/cloudfoundry-cli.list
    sudo apt-get update
    sudo apt-get install cf8-cli
    echo "CF CLI installed"
fi

echo "Updating git info for environment in process"
echo "Branch: $BRANCH"
echo "Commit: $COMMIT"
echo "TAG: ${TAG:-none}"
echo "Environment: $ENVIRONMENT"

if [[ "$ENVIRONMENT" == "stable" || "$ENVIRONMENT" == "staging" ]]; then
    APP_NAME="$ENVIRONMENT"
else
    APP_NAME="getgov-${ENVIRONMENT}"
fi

if [ $IS_CI = true ]; then
    echo "Authenticating..."
    cf api api.fr.cloud.gov
    if ! cf auth "$CF_USERNAME" "$CF_PASSWORD"; then
    echo "ERROR: Auth failed"
    echo "Please check credentials"
    fi
fi

echo "Setting env variables"
cf target -o cisa-dotgov -s "$ENVIRONMENT"
cf set-env $APP_NAME GIT_BRANCH "$BRANCH"
cf set-env $APP_NAME GIT_COMMIT "$COMMIT"
cf set-env $APP_NAME GIT_TAG "$TAG"

echo "Git info Updated for $ENVIRONMENT"

if [ "$IS_CI" = false ]; then
    echo "app is restaging for changes to take effect"
    cf restage "getgov-$ENVIRONMENT"
fi