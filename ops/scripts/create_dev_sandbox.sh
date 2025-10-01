# This script sets up a completely new Cloud.gov CF Space with all the corresponding
# infrastructure needed to run get.gov. It can serve for documentation for running
# NOTE: This script was written for MacOS and to be run at the root directory. 

if [ -z "$1" ]; then
    echo 'Please specify a new space to create (i.e. lmm)' >&2
    exit 1
fi

if [ ! $(command -v gh) ] || [ ! $(command -v jq) ] || [ ! $(command -v cf) ]; then
    echo "jq, cf, and gh packages must be installed. Please install via your preferred manager."
    exit 1
fi

upcase_name=$(printf "%s" "$1" | tr '[:lower:]' '[:upper:]')

read -p "Are you on a new branch? We will have to commit this work. (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    git checkout -b new-dev-sandbox-$1
fi

cf target -o cisa-dotgov

read -p "Are you logged in to the cisa-dotgov CF org above? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    cf login -a https://api.fr.cloud.gov --sso
fi

gh auth status
read -p "Are you logged into a Github account with access to cisagov/getgov? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    gh auth login
fi

echo "Creating manifest for $1..."
cp ops/scripts/manifest-sandbox-template.yaml ops/manifests/manifest-$1.yaml
sed -i '' "s/ENVIRONMENT/$1/" "ops/manifests/manifest-$1.yaml"

echo "Adding new environment to settings.py..."
sed -i '' '/getgov-development.app.cloud.gov/ {a\
    '\"getgov-$1.app.cloud.gov\"',
}' src/registrar/config/settings.py

echo "Creating new cloud.gov space for $1..."
cf create-space $1
cf target -o "cisa-dotgov" -s $1
cf bind-security-group public_networks_egress cisa-dotgov --space $1
cf bind-security-group trusted_local_networks_egress cisa-dotgov --space $1

echo "Creating new cloud.gov DB for $1. This usually takes about 5 minutes..."
cf create-service aws-rds micro-psql getgov-$1-database -w

echo "Creating new cloud.gov credentials for $1..."
django_key=$(python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
openssl req -nodes -x509 -days 365 -newkey rsa:2048 -keyout private-$1.pem -out public-$1.crt
login_key=$(base64 -i private-$1.pem)
jq -n --arg django_key "$django_key" --arg login_key "$login_key" '{"DJANGO_SECRET_KEY":$django_key,"DJANGO_SECRET_LOGIN_KEY":$login_key}' > credentials-$1.json
cf cups getgov-credentials -p credentials-$1.json

echo "Now you will need to update some things for Login. Please sign-in to https://dashboard.int.identitysandbox.gov/."
echo "Navigate to our application config: https://dashboard.int.identitysandbox.gov/service_providers/2640/edit?"
echo "There are two things to update."
echo "1. You need to upload the public-$1.crt file generated as part of the previous command."
echo "2. You need to add two redirect URIs: https://getgov-$1.app.cloud.gov/openid/callback/login/ and
https://getgov-$1.app.cloud.gov/openid/callback/logout/ to the list of URIs."
read -p "Please confirm when this is done (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    exit 1
fi

echo "Now we should add the OT&E registry credentials. The credentials can be found in other sandboxes."
echo "To edit credentials, log into cloud.gov and navigate to the space created."
echo "On the left sidebar, click on User Services. "
echo "Click on the 3 dots at the end of the getgov-credentials line and select edit"
echo "Add the appropriate credentials and click Finish."
read -p "Please confirm when this is done (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    exit 1
fi

echo "Database create succeeded and credentials created. Deploying the get.gov application to the new space $1..."
echo "Building assets..."
open -a Docker
cd src/
./build.sh
cd ..
cf push getgov-$1 -f ops/manifests/manifest-$1.yaml

echo "Creating cache table..."
cf run-task getgov-$1 --command 'python manage.py createcachetable' --name createcachetable

read -p "Please provide the email of the space developer: " -r
cf set-space-role $REPLY cisa-dotgov $1 SpaceDeveloper

read -p "Should we run migrations? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    cf run-task getgov-$1 --command 'python manage.py migrate' --name migrate
fi

echo "Alright, your app is up and running at https://getgov-$1.app.cloud.gov!"
echo
echo "Moving on to setup Github automation..."

echo "Adding new environment to Github Actions..."
sed -i '' '/          - development/ {a\
          - '"$1"'
}' .github/workflows/reset-db.yaml

sed -i '' '/          - development/ {a\
          - '"$1"'
}' .github/workflows/migrate.yaml

sed -i '' '/          - backup/ {a\
          - '"$1"'
}' .github/workflows/deploy-manual.yaml

sed -i '' "/startsWith(github.head_ref, \'backup/ {a\\
        || startsWith(github.head_ref, '"$1"')
}" .github/workflows/deploy-sandbox.yaml

sed -i '' '/          - backup/ {a\
          - '"$1"'
}' .github/workflows/createcachetable.yaml

sed -i '' '/          - backup/ {a\
          - '"$1"'
}' .github/workflows/delete-and-recreate-db.yaml

sed -i '' '/          - backup/ {a\
          - '"$1"'
}' .github/workflows/load-fixtures.yaml

echo "Creating space deployer for Github deploys..."
cf create-service cloud-gov-service-account space-deployer github-cd-account
cf create-service-key github-cd-account github-cd-key
cf service-key github-cd-account github-cd-key
read -p "Please confirm we should set the above username and key to Github secrets. (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    exit 1
fi

cf service-key github-cd-account github-cd-key | sed 1,2d  | jq -r '[.credentials.username, .credentials.password]|@tsv' |

while read -r username password; do
    gh secret --repo cisagov/getgov set CF_${upcase_name}_USERNAME --body $username
    gh secret --repo cisagov/getgov set CF_${upcase_name}_PASSWORD --body $password
done

read -p "All done! Should we open a PR with these changes? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    git add ops/manifests/manifest-$1.yaml .github/workflows/ src/registrar/config/settings.py 
    git commit -m "Add new developer sandbox '"$1"' infrastructure"
    gh pr create
fi
