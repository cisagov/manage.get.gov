# Container image that runs your code
FROM python:3-buster

# Copies your code file from your action repository to the filesystem path `/` of the container
COPY entrypoint.sh /entrypoint.sh
# Mount suppression.xml to remove known false positives from OWASP
COPY suppression.xml /src/suppression.xml

# Code file to execute when the docker container starts up (`entrypoint.sh`)
ENTRYPOINT ["/entrypoint.sh"]

CMD ["dependency-check.sh", "--scan", "/app", "--format", "HTML", "--out", "/app/owasp-report", "--suppression", "/src/suppression.xml"]
