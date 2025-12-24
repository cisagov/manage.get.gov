#!/bin/sh

echo "Updating git info for environment in process"
echo " Branch: $BRANCH"
echo " Commit: $COMMIT"
echo " TAG: ${TAG:-none}"

if [[ "$ENVIRONMENT" == "stable" || "$ENVIRONMENT" == "staging" ]]; then
    APP_NAME="$ENVIRONMENT"
else
    APP_NAME="getgov-${ENVIRONMENT}"
fi


cf set-env $APP_NAME GIT_BRANCH "$BRANCH"
cf set-env $APP_NAME GIT_COMMIT "$COMMIT"
cf set-env $APP_NAME GIT_TAG "$TAG"

echo "Git info Updated for $ENVIRONMENT"