FROM docker.io/cimg/node:current-browsers
FROM node:21.7.3
WORKDIR /app

# Install app dependencies
# A wildcard is used to ensure both package.json AND package-lock.json are copied
# where available (npm@5+)
COPY --chown=circleci:circleci package*.json ./


RUN npm install -g npm@10.5.0
RUN npm install