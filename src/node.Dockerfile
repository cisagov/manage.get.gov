FROM docker.io/cimg/node:current-browsers
WORKDIR /app

# Install gosu
USER root
RUN apt-get update && \
    apt-get install -y gosu && \
    rm -rf /var/lib/apt/lists/*

# Install app dependencies
# A wildcard is used to ensure both package.json AND package-lock.json are copied
# where available (npm@5+)
COPY --chown=circleci:circleci package*.json ./