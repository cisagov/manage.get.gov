FROM docker.io/cimg/node:18.20-browsers
WORKDIR /app

# Install app dependencies
# A wildcard is used to ensure both package.json AND package-lock.json are copied
# where available (npm@5+)
COPY --chown=circleci:circleci package*.json ./

RUN npm install