FROM python:3.10

# Python 3.11 introduces a bug in oic package, fyi - Oct 31, 2022

RUN apt-get update && apt-get install -y postgresql-client ca-certificates curl && update-ca-certificates && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY Pipfile Pipfile
COPY Pipfile.lock Pipfile.lock

RUN pip install pipenv --no-cache-dir pipenv
ENV SSL_CERT_FILE=/usr/local/lib/python3.10/site-packages/certifi/cacert.pem
ENV REQUESTS_CA_BUNDLE=/usr/local/lib/python3.10/site-packages/certifi/cacert.pem

RUN pipenv sync --system --dev
