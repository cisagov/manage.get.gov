# This script rotates the login.gov credentials, DJANGO_SECRET_KEY and DJANGO_SECRET_LOGIN_KEY that allow for identity sandbox to work on sandboxes and local.
# The echo prints in this script should serve for documentation for running manually.
# NOTE: This script was written for MacOS and to be run at the root directory. 

if [ -z "$1" ]; then
    echo 'Please specify a new space to create (i.e. lmm)' >&2
    exit 1
fi

if [ ! $(command -v jq) ] || [ ! $(command -v cf) ]; then
    echo "jq, and cf packages must be installed. Please install via your preferred manager."
    exit 1
fi

cf target -o cisa-dotgov

read -p "Are you logged in to the cisa-dotgov CF org above? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    cf login -a https://api.fr.cloud.gov --sso
fi
echo "targeting space"
cf target -o "cisa-dotgov" -s $1

echo "Creating new login.gov credentials for $1..."
django_key=$(python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
openssl req -nodes -x509 -days 365 -newkey rsa:2048 -keyout private-$1.pem -out public-$1.crt
login_key=$(base64 -i private-$1.pem)
jq -n --arg django_key "$django_key" --arg login_key "$login_key" '{"DJANGO_SECRET_KEY":$django_key,"DJANGO_SECRET_LOGIN_KEY":$login_key}' > credentials-$1.json
# cf uups getgov-credentials -p credentials-$1.json

# echo "Now you will need to update some things for Login. Please sign-in to https://dashboard.int.identitysandbox.gov/."
# echo "Navigate to our application config: https://dashboard.int.identitysandbox.gov/service_providers/2640/edit?"
# echo "There are two things to update."
# echo "1. Remove the old cert associated with the user's email (under Public Certificates)"
# echo "2. You need to upload the public-$1.crt file generated as part of the previous command. See the "choose cert file" button under Public Certificates."

# echo "Then, tell the developer to update their local .env file by retreiving their credentials from the sandbox"
