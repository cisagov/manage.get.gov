# Image for the `playwright` docker-compose service. Extends the same node
# base as `node` and `pa11y`, plus the bits needed to run a *visible* browser
# inside the container — Xvfb (virtual display), x11vnc (shares it), and
# websockify+novnc (lets you watch it from your host browser).
FROM --platform=linux/amd64 docker.io/cimg/node:current-browsers

USER root

# Xvfb is already in the base image; this adds VNC + the noVNC web client.
RUN apt-get update && apt-get install -y --no-install-recommends \
        x11vnc \
        novnc \
        websockify \
        fluxbox \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --chown=circleci:circleci package*.json ./
