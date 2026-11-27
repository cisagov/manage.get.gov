#!/bin/bash

npm install
npm rebuild
# Pre-fetch Chromium for the playwright service (no-op if already cached).
if [ -d "./node_modules/@playwright/test" ]; then
  npx playwright install chromium --with-deps 2>/dev/null || npx playwright install chromium
fi
dir=./registrar/assets
if [ -d "$dir" ]
then
  echo "Compiling USWDS assets"
	npx gulp copyAssets
  npx gulp compile
else
  echo "Initial USWDS assets build"
  npx gulp init
  npx gulp compile
fi
npx gulp watchAll
