# HOWTO Rotate the Application's Secrets
========================

Secrets are read from the running environment.

Secrets were originally created with:

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

## DJANGO_SECRET_KEY

This is a standard Django secret key. See Django documentation for tips on generating a new one. 

## DJANGO_SECRET_LOGIN_KEY

This is the base64 encoded private key used in the OpenID Connect authentication flow with Login.gov. It is used to sign a token during user login; the signature is examined by Login.gov before their API grants access to user data.

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

These are the login credentials for accessing the registry.

## REGISTRY_CERT and REGISTRY_KEY and REGISTRY_KEY_PASSPHRASE

These are the client certificate and its private key used to identify the registrar to the registry during the establishment of a TCP connection.

The private key is protected by a passphrase for safer transport and storage.

These were generated with the following steps:

### Step 1: Generate an unencrypted private key with a named curve

```bash
openssl ecparam -name prime256v1 -genkey -out client_unencrypted.key
```

### Step 2: Create an encrypted private key with a passphrase

```bash
openssl pkcs8 -topk8 -v2 aes-256-cbc -in client_unencrypted.key -out client.key
```

### Generate the certificate

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

You'll need to give the new certificate to the registry vendor _before_ rotating it in production. Once it has been accepted by the vendor, make sure to update the kdbx file on Google Drive.

## REGISTRY_HOSTNAME

This is the hostname at which the registry can be found.

## SECRET_METADATA_KEY

This is the passphrase for the zipped and encrypted metadata email that is sent out daily. Reach out to product team members or leads with access to security passwords if the passcode is needed.

To change the password, use a password generator to generate a password, then update the user credentials per the above instructions. Be sure to update the [KBDX](https://docs.google.com/document/d/1_BbJmjYZNYLNh4jJPPnUEG9tFCzJrOc0nMrZrnSKKyw) file in Google Drive with this password change. 


