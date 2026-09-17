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
The DJANGO_SECRET_KEY and DJANGO_SECRET_LOGIN_KEY are reset once a year for each sandbox, see their sections below for more information on them and how to manually generate these keys. To save time, complete the following steps to rotate these credentials using a script:

### 🚨 DO NOT DO THE FOLLOWING IN PRODUCTION, GO TO THE PRODUCTION ONLY SECTION 🚨

### Non-Prod steps:

#### Step 1 login

To run the script make sure you are logged on the cf cli and make sure you have access to the [Login Partner Dashboard](https://dashboard.int.identitysandbox.gov/service_providers/2640).

#### Step 2 Run the script

Run the following where "ENV" refers to whichever sandbox you want to reset credentials on. Note, the below assumes you are in the root directory of our app.

```bash
ops/scripts/rotate_login_certs.sh ENV
```

#### Step 3 Respond to the terminal prompts

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

#### Step 4 Delete the old cert

Navigate to to the Login Partner Dashboard linked above and delete the old cert

#### Step 5 add the new cert

In whichever directory you ran the script there should now be a .crt file named "public-ENV.crt", where ENV is the space name you used on Step 2. Upload this cert in the Login Partner Dashboard in the same section where you deleted the old one.

### Production only

The script never updates or restages production. Run with `stable` it backs up the current credentials, generates the new key and cert, writes `credentials-stable.json`, and stops. Everything after that is manual, and production is updated LAST, only after Login.gov confirms the new cert.

#### (Prod) Step 1: Run the script

Make sure you are logged in to the cf cli and have access to the production [Login Partner Dashboard](https://dashboard.login.gov/). From the root directory of our app run:

```bash
ops/scripts/rotate_login_certs.sh stable
```

Respond to the prompts. For the cert information, "Common Name" is `stable` and "Email Address" is whoever is running this rotation:

```bash
Country Name (2 letter code) [AU]:US
State or Province Name (full name) [Some-State]:DC
Locality Name (eg, city) []:DC
Organization Name (eg, company) [Internet Widgits Pty Ltd]:DHS
Organizational Unit Name (eg, section) []:CISA
Common Name (e.g. server FQDN or YOUR name) []:stable
Email Address []: example@something.com
```

The script leaves four files in the directory you ran it from:

- `credentials-stable-backup.json` - the current production credentials, untouched. This is your rollback.
- `credentials-stable.json` - the same credentials with the new `DJANGO_SECRET_KEY` and `DJANGO_SECRET_LOGIN_KEY` merged in. Nothing has been uploaded.
- `private-stable.pem` and `public-stable.crt` - the new key pair.

#### (Prod) Step 2: Check the files

Do not skip this, a bad cert or a mismatched key will lock every user out of production.

1.) Confirm the backup exists and holds the current credentials. If it is missing, empty, or `null`, make it by hand using the section below before going any further

```bash
jq . credentials-stable-backup.json
```

2.) Confirm the private key parses, this should print "RSA key ok"

```bash
openssl rsa -in private-stable.pem -check -noout
```

3.) Confirm the cert and the private key are a matching pair. Both commands MUST print the exact same hash

```bash
openssl x509 -noout -modulus -in public-stable.crt | openssl md5
openssl rsa -noout -modulus -in private-stable.pem | openssl md5
```

4.) Confirm `DJANGO_SECRET_KEY` and `DJANGO_SECRET_LOGIN_KEY` are the ONLY values that differ between the two json files

```bash
diff <(jq -S . credentials-stable-backup.json) <(jq -S . credentials-stable.json)
```

##### Making the backup by hand

In terminal run:

```bash
cf env getgov-stable | awk '/VCAP_SERVICES: /,/^$/' | sed s/VCAP_SERVICES:// | jq '."user-provided"[0].credentials' > credentials-stable-backup.json
```

Alternatively, you can do the following:

- Go to [cloud.gov dashboard](https://dashboard.fr.cloud.gov/home)
- Under `Applications` click `getgov-stable`
- Click `Services`
- Click the three dots next to `getgov-credentials` and select `edit`
- Highlight and copy all the credentials shown, and save locally as `credentials-stable-backup.json`. Remember to delete this once all steps are done.

#### (Prod) Step 3: Save the files and secrets

Save `private-stable.pem`, `public-stable.crt`, the new `DJANGO_SECRET_KEY`, and the new `DJANGO_SECRET_LOGIN_KEY` to the [KBDX](https://docs.google.com/document/d/1_BbJmjYZNYLNh4jJPPnUEG9tFCzJrOc0nMrZrnSKKyw) file on Google Drive, labeled with this year's date. Keep the previous year's entries, they are what you roll back to.

#### (Prod) Step 4: Upload the cert to login.gov

🚨 Do NOT delete the old cert🚨. Production keeps authenticating with it until Login.gov applies the new one, so both need to exist side by side for now.

1.) Sign in to the production Login Partner Dashboard at https://dashboard.login.gov/
2.) Open our production config (named `get.gov` currently)
3.) Click edit, and under "Public Certificates" use the "choose cert file" button to upload `public-stable.crt`
4.) Leave the existing cert in place and save

Unlike the sandbox, saving does not apply the change. Login.gov has to apply it, which is what the next step is for.

#### (Prod) Step 5: Submit a ticket

Open a ticket with Login.gov partner support asking them to apply the new cert. Include:

1.) Our issuer: `urn:gov:cisa:openidconnect.profiles:sp:sso:cisa:dotgov_registrar`
2.) The environment: production (`manage.get.gov`)
3.) That the uploaded cert needs to be applied, and that the old cert should stay until we confirm the new one works

Then WAIT for their reply. Updating our side first breaks logins for everyone.

#### (Prod) Step 6: Update the production credentials

Only do this after Login.gov confirms the new cert is applied.

##### Option 1) Changing with the UI

The editor replaces the ENTIRE credentials json, so every other key has to stay exactly as it is.

1.) Go to [cloud.gov dashboard](https://dashboard.fr.cloud.gov/home)
2.) Under `Applications` click `getgov-stable`
3.) Click `Services`
4.) Click the three dots next to `getgov-credentials` and select `edit`
5.) Replace ONLY the `DJANGO_SECRET_KEY` and `DJANGO_SECRET_LOGIN_KEY` values with the new ones from `credentials-stable.json`
6.) Compare against your backup before saving, those two values are the only ones that should differ
7.) Click `Finish` to save
8.) Saving does not reach the running app, it has to be restaged. In terminal run:

```bash
cf target -o cisa-dotgov -s stable
cf restage getgov-stable --strategy rolling
```

9.) Once the restage finishes, log in to https://manage.get.gov/ to confirm login still works

##### Option 2) Changing in terminal

1.) Target the production space

```bash
cf target -o cisa-dotgov -s stable
```

2.) Upload `credentials-stable.json` from Step 1 and restage

```bash
cf uups getgov-credentials -p credentials-stable.json
cf restage getgov-stable --strategy rolling
```

3.) Once the restage finishes, log in to https://manage.get.gov/ to confirm login still works

#### (Prod) Step 7: Clean up

1.) Once you have confirmed login works, go back to the production Login Partner Dashboard and delete the old cert under "Public Certificates"
2.) Double check you have updated the KBDX file with all the correct data
3.) Delete any credentials saved locally on your machine such as: `credentials-stable.json`, `credentials-stable-backup.json`, `private-stable.pem`, and `public-stable.crt`.


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

These are the login credentials for accessing the registry and they are set by Cloudflare. Cloudflare should notify us if and when registry credentials ever need to be changed.

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


