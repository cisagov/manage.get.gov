# node v20.6.0
FROM docker.io/cimg/node:current-browsers@sha256:01b628bd45035abd1ae517587902db3a40553a458395b90f323867234a5f06b4
WORKDIR /app

USER root

# Install app dependencies
# A wildcard is used to ensure both package.json AND package-lock.json are copied
# where available (npm@5+)
COPY --chown=circleci:circleci package*.json ./ 