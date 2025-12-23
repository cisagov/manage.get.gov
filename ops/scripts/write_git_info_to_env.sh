echo "Updating git info for environment in process"
echo " Branch: $BRANCH"
echo " Commit: $COMMIT"
echo " TAG: ${TAG:-none}"

echo "Authenticating"
cf api api.fr.cloud.gov
cf auth "$CF_USERNAME" "$CF_PASSWORD"
cf target -o cisa-dotgov -s $ENVIRONMENT
if [[ "$ENVIRONMENT" == "stable" || "$ENVIRONMENT" == "staging"]]; then
    APP_NAME=$ENVIRONMENT
else
    APP_NAME="getgov-${ENVIRONMENT}"


cf set-env $APP_NAME GIT_BRANCH "$BRANCH"
cf set-env $APP_NAME GIT_COMMIT "$COMMIT"
cf set-env $APP_NAME GIT_TAG "$TAG"

echo "Git info Updated for $ENVIRONMENT"