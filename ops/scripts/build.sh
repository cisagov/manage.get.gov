#!/bin/sh

# Compile assets
docker compose run node npx gulp compile;
docker compose run node npx gulp copyAssets;

# Collect assets
docker compose build
docker compose run app python manage.py collectstatic --noinput
