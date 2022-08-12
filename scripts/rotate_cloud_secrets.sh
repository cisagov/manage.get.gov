# NOTE: This script does not work with cf v8. We recommend using cf v7 for all cloud.gov commands.
if [ ! $(command -v gh) ] || [ ! $(command -v jq) ] || [ ! $(command -v cf) ]; then
  echo "jq, cf, and gh packages must be installed. Please install via your preferred manager."
  exit 1
fi

cf spaces
read -p "Are you logged in to the dotgov-poc CF space above? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    cf login -a https://api.fr.cloud.gov --sso
fi

gh auth status
read -p "Are you logged into a Github account with access to cisagov/dotgov? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    gh auth login
fi

echo "Great, removing and replacing Github CD account..."
cf delete-service-key github-cd-account github-cd-key
cf create-service-key github-cd-account github-cd-key
cf service-key github-cd-account github-cd-key
read -p "Please confirm we should set the above username and key to Github secrets. (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    exit 1
fi

cf service-key github-cd-account github-cd-key | sed 1,2d  | jq -r '[.username, .password]|@tsv' | 
while read -r username password; do
    gh secret --repo cisagov/dotgov set CF_USERNAME --body $username
    gh secret --repo cisagov/dotgov set CF_PASSWORD --body $password
done
