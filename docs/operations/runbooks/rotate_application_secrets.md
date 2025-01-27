# HOWTO Rotate the Application's Secrets
========================

Below you will find sections for each of the application secrets which can & will be changed individually and expire at different times. Secrets are read from the running environment.

Secrets are originally created with:

```sh
cf cups getgov-credentials -p credentials-<ENVIRONMENT>.json
```

Where `credentials-<ENVIRONMENT>.json` looks like:

```json
{
  "DJANGO_SECRET_KEY": "EXAMPLE",
  "DJANGO_SECRET_LOGIN_KEY": "EXAMPLE",
  "AWS_ACCESS_KEY_ID": "EXAMPLE",
  "AWS_SECRET_ACCESS_KEY": "EXAMPLE",
  ...
}
```

(Specific credentials are mentioned below.)

You can see the current environment with `cf env <APP>`, for example `cf env getgov-stable`.

The commands `cups` and `uups` stand for [`create user provided service`](https://docs.cloudfoundry.org/devguide/services/user-provided.html) and `update user provided service`. User provided services are the way currently recommended by Cloud.gov for deploying secrets. The user provided service is bound to the application in `manifest-<ENVIRONMENT>.json`.

To rotate secrets, create a new `credentials-<ENVIRONMENT>.json` file, upload it, then restage the app.

Example:

```bash
cf update-user-provided-service getgov-credentials -p credentials-stable.json
cf restage getgov-stable --strategy rolling
```

Non-secret environment variables can be declared in `manifest-<ENVIRONMENT>.json` directly.

## Rotating login.gov credentials
The DJANGO_SECRET_KEY and DJANGO_SECRET_LOGIN_KEY are reset once a year for each sandbox, see their sections below for more information on them and how to manually generate these keys. To save time, complete the following steps to rotate these credentials using a script in non-production environments:

### Step 1 login

To run the script make sure you are logged on the cf cli and make sure you have access to the [Login Partner Dashboard](https://dashboard.int.identitysandbox.gov/service_providers/2640). 

### Step 2 Run the script

Run the following where "ENV" refers to whichever sandbox you want to reset credentials on. Note, the below assumes you are in the root directory of our app.

```bash
ops/scripts/rotate_login_certs.sh ENV
```

### Step 3 Respond to the terminal prompts

Respond to the prompts from the script and, when it asks for the cert information, the below is an example of what you should enter. Note for "Common Name" you should put the name of the sandbox and for "Email Address" it should be the address of who owns that sandbox (such as the developer's email, if it's a develop sandbox, or whoever ran this action otherwise)

```bash
Country Name (2 letter code) [AU]:US
State or Province Name (full name) [Some-State]:DC
Locality Name (eg, city) []:DC
Organization Name (eg, company) [Internet Widgits Pty Ltd]:DHS
Organizational Unit Name (eg, section) []:CISA
Common Name (e.g. server FQDN or YOUR name) []:ENV
Email Address []: example@something.com
```

Note when this script is done it will have generated a .pem and a .crt file, as well as updated the cert info on the sandbox

### Step 4 Delete the old cert

Navigate to to the Login Partner Dashboard linked above and delete the old cert

### Step 5 add the new cert

In whichever directory you ran the script there should now be a .crt file named "public-ENV.crt", where ENV is the space name you used on Step 2. Upload this cert in the Login Partner Dashboard in the same section where you deleted the old one.

### Production only

This script should not be run in production. Instead, you will need to manually create the keys and then refrain from updating the sandbox. Once the cert is created you will upload it to the Login Partner Dashboard for our production system, and then open a ticket with them to update our existing Login.gov integration. Once they respond back saying it has been applied, you can then update the sandbox.

## DJANGO_SECRET_KEY

This is a standard Django secret key. See Django documentation for tips on generating a new one. 

## DJANGO_SECRET_LOGIN_KEY

This is the base64 encoded private key used in the OpenID Connect authentication flow with Login.gov. It is used to sign a token during user login; the signature is examined by Login.gov before their API grants access to user data.

### Manually creating creating the Login Key
Generate a new key using this command (or whatever is most recently [recommended by Login.gov](https://developers.login.gov/testing/#creating-a-public-certificate)):

```bash
openssl req -nodes -x509 -days 365 -newkey rsa:2048 -keyout private.pem -out public.crt
```

Encode it using:

```bash
base64 private.pem
```

You also need to upload the `public.crt` key if recently created to the login.gov identity sandbox: https://dashboard.int.identitysandbox.gov/



## AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

To access the AWS Simple Email Service, we need credentials from the CISA AWS
account for an IAM user who has limited access to only SES. Those credentials
need to be specified in the environment.

## REGISTRY_CL_ID and REGISTRY_PASSWORD

These are the login credentials for accessing the registry and they are set by cloudflare. They should notify us if and when these ever need to be changed.

## Rotating REGISTRY_CERT, REGISTRY_KEY, and REGISTRY_KEY_PASSPHRASE for Cloudflare environments

These are the client certificate and its private key used to identify the registrar to the registry during the establishment of a TCP connection.

The private key is protected by a passphrase for safer transport and storage.

Note this must be reset once a year.

These were generated with the following steps:

### Step 1: Generate an unencrypted private key with a named curve

```bash
openssl ecparam -name prime256v1 -genkey -out client_unencrypted.key
```

### Step 2: Create an encrypted private key with a passphrase

```bash
openssl pkcs8 -topk8 -v2 aes-256-cbc -in client_unencrypted.key -out client.key
```

### Step 3: Generate the certificate

```bash
openssl req -new -x509 -days 365 -key client.key -out client.crt -subj "/C=US/ST=DC/L=Washington/O=GSA/OU=18F/CN=GOV Prototype Registrar"
```

(If you can't use openssl on your computer directly, you can access it using Docker as `docker run --platform=linux/amd64 -it --rm -v $(pwd):/apps -w /apps alpine/openssl`.)

Encode them using:

```bash
base64 client.key
base64 client.crt
```

Note depending on your system you may need to instead run:

```bash
base64 -i client.key
base64 -i client.crt
```

You'll need to give the new certificate to the registry vendor _before_ rotating it in production. Once it has been accepted by the vendor, make sure to update [the KBDX](https://docs.google.com/document/d/1_BbJmjYZNYLNh4jJPPnUEG9tFCzJrOc0nMrZrnSKKyw) file on Google Drive.

## REGISTRY_HOSTNAME

This is the hostname at which the registry can be found.

## SECRET_METADATA_KEY

This is the passphrase for the zipped and encrypted metadata email that is sent out daily. Reach out to product team members or leads with access to security passwords if the passcode is needed.

To change the password, use a password generator to generate a password, then update the user credentials per the above instructions. Be sure to update the [KBDX](https://docs.google.com/document/d/1_BbJmjYZNYLNh4jJPPnUEG9tFCzJrOc0nMrZrnSKKyw) file in Google Drive with this password change. 


