FROM python:3.14@sha256:22caa054c0d309b1eee6f448326a8821a674a75b98653247fe706db90491fc87

RUN apt-get update && apt-get install -y postgresql-client

COPY Pipfile Pipfile
COPY Pipfile.lock Pipfile.lock

RUN pip install pipenv
RUN pipenv sync --system --dev
