# This script sets up a completely new Cloud.gov CF Space with all the corresponding
# infrastructure needed to run get.gov. It can serve for documentation for running
# NOTE: This script was written for MacOS and to be run at the root directory
# of the repository.

if [ -z "$1" ]; then
    echo 'Please specify a name on the command line for the new space (i.e. lmm)' >&2
    exit 1
fi

# The user running this script has to be a SpaceDeveloper on both the
# new and old org/spaces.

OLD_ORG="cisa-getgov-prototyping"
NEW_ORG="cisa-dotgov"

#
# delete old route
cf target -o $OLD_ORG -s $1
cf delete-route app.cloud.gov -n getgov-$1

# re-claim the route on new orf
cf target -o $NEW_ORG -s $1
cf map-route getgov-$1 app.cloud.gov -n getgov-$1
cf delete-route app.cloud.gov -n getgov-$1-migrate

# delete old app and services
cf target -o $OLD_ORG -s $1
cf delete getgov-$1
cf delete-service getgov-$1-database
cf delete-service getgov-credentials
cf delete-service getgov-cd-account
cf delete-space $1


printf "Remove -migrate from ops/manifests/manifest-$1.yaml"
