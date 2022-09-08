#!/bin/bash
npm install
npm rebuild
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
npx gulp watch
