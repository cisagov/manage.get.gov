ENVIRONMENT=$1
BRANCH=$2
COMMIT=$3
TAG=${4:-""}


echo "Updating git info for environment in process"
echo " Branch: $BRANCH"
echo " Commit: $COMMIT"
echo " TAG: ${TAG:-none}"

echo "Authenticating"
cf api api.fr.cloud.gov
cf auth "$CF_USERNAME" "$CF_PASSWORD"
cf target -o cisa-dotgov -s $ENVIRONMENT
cf set-env $ENVIRONMENT GIT_BRANCH "$BRANCH"
cf set-env $ENVIRONMENT GIT_COMMIT "$COMMIT"
cf set-env $ENVIRONMENT GIT_TAG "$TAG"

echo "Git info Updated for $ENVIRONMENT"