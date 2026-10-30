FROM docker.io/cimg/node:current-browsers
WORKDIR /app

USER root

COPY zscaler-root.pem /usr/local/share/ca-certificates/zscaler-root.crt

RUN update-ca-certificates

ENV NODE_EXTRA_CA_CERTS=/usr/local/share/ca-certificates/zscaler-root.crt

# Install app dependencies
# A wildcard is used to ensure both package.json AND package-lock.json are copied
# where available (npm@5+)
COPY --chown=circleci:circleci package*.json ./