# HOWTO Add secrets to an existing sandbox


### Check if you need to add secrets
Run this command to get the environment variables from a sandbox:

```sh
cf env <APP>
```
For example `cf env getgov-development`

Check that these environment variables exist:
```
{
  "DJANGO_SECRET_KEY": "EXAMPLE",
  "DJANGO_SECRET_LOGIN_KEY": "EXAMPLE",
  "AWS_ACCESS_KEY_ID": "EXAMPLE",
  "AWS_SECRET_ACCESS_KEY": "EXAMPLE",
  "REGISTRY_KEY": "EXAMPLE,
  ...
}
```

If those variable are not present, use the following steps to set secrets by creating a new `credentials-<ENVIRONMENT>.json` file and uploading it.
(Note that many of these commands were taken from the [`create_dev_sandbox.sh`](../../../ops/scripts/create_dev_sandbox.sh) script and were tested on MacOS)

### Create a new Django key
```sh
django_key=$(python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
```

### Replace the existing certificate 
Create a certificate:
```sh
openssl req -nodes -x509 -days 365 -newkey rsa:2048 -keyout private-<ENVIRONMENT>.pem -out public-<ENVIRONMENT>.crt
```

Fill in the following for the prompts:

Note: for "Common Name" you should put the name of the sandbox and for "Email Address" it should be the address of who owns that sandbox (such as the developer's email, if it's a developer sandbox, or whoever ran this action otherwise)

```sh
Country Name (2 letter code) [AU]: US
State or Province Name (full name) [Some-State]: DC
Locality Name (eg, city) []: DC
Organization Name (eg, company) [Internet Widgits Pty Ltd]: DHS
Organizational Unit Name (eg, section) []: CISA
Common Name (e.g. server FQDN or YOUR name) []: <ENVIRONMENT>
Email Address []: <example@something.com>
```
Go to https://dashboard.int.identitysandbox.gov/service_providers/2640/edit to remove the old certificate and upload the new one. 

### Create the login key
```sh
login_key=$(base64 -i private-<ENVIRONMENT>.pem)
```

### Create the credentials file
```sh
jq -n --arg django_key "$django_key" --arg login_key "$login_key" '{"DJANGO_SECRET_KEY":$django_key,"DJANGO_SECRET_LOGIN_KEY":$login_key}' > credentials-<ENVIRONMENT>.json
```

Copy `REGISTRY_*` credentials from another sandbox into your `credentials-<ENVIRONMENT>.json` file.  Also add your `AWS_*` credentials if you have them, otherwise also copy them from another sandbox. You can either use the cloud.gov dashboard or the command `cf env <APP>` to find other credentials.

### Update the `getgov-credentials` service tied to your environment.
```sh
cf uups getgov-credentials -p credentials-<ENVIRONMENT>.json
```

### Restage your application
```sh
cf restage getgov-<ENVIRONMENT> --strategy rolling
```