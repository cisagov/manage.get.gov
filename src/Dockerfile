FROM python:3.10

# Python 3.11 introduces a bug in oic package, fyi - Oct 31, 2022

RUN apt-get update && apt-get install -y postgresql-client

COPY Pipfile Pipfile
COPY Pipfile.lock Pipfile.lock

RUN pip install pipenv
RUN pipenv sync --system --dev

# Mount suppression.xml to remove known false positives from OWASP
COPY suppression.xml /src/suppression.xml
CMD ["dependency-check.sh", "--scan", "/app", "--format", "HTML", "--out", "/app/owasp-report", "--suppression", "/src/suppression.xml"]
