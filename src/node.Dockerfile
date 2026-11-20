FROM docker.io/cimg/node:26.13.0-browsers@sha256:01b628bd45035abd1ae517587902db3a40553a458395b90f323867234a5f06b4
WORKDIR /app

USER root

COPY zscaler-root.pem* /usr/local/share/ca-certificates/zscaler-root.crt

RUN update-ca-certificates

ENV NODE_EXTRA_CA_CERTS=/usr/local/share/ca-certificates/zscaler-root.crt

# Install app dependencies
# A wildcard is used to ensure both package.json AND package-lock.json are copied
# where available (npm@5+)
COPY --chown=circleci:circleci package*.json ./