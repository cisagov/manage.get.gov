/* gulpfile.js */

const uswds = require('@uswds/compile');
const {promises} = require('fs')
const { src, dest, series } = require('gulp');

/**
 * USWDS version
 * Set the version of USWDS you're using (2 or 3)
 */

uswds.settings.version = 3;

/**
 * Path settings
 * Set as many as you need
 */

const ASSETS_DIR = './registrar/assets/';

uswds.paths.dist.css = ASSETS_DIR + 'css';
uswds.paths.dist.sass = ASSETS_DIR + 'sass';
uswds.paths.dist.theme = ASSETS_DIR + 'sass/_theme';
uswds.paths.dist.fonts = ASSETS_DIR + 'fonts';
uswds.paths.dist.js = ASSETS_DIR + 'js';
uswds.paths.dist.img = ASSETS_DIR + 'img';

/**
 * Exports
 * Add as many as you need
 */

exports.default = uswds.compile;
exports.init = uswds.init;
exports.compile = uswds.compile;
exports.watch = uswds.watch;
exports.copyAssets = uswds.copyAssets
                                                                                  
// THIS IS A TEMPORARY WORKAROUND. Delete lines 4-17 after this lands in the node releases
// https://github.com/nodejs/node/issues/52707#issue-2265785789
// This solution was inspired by this change:
// https://github.com/nodejs/node/issues/52707#issuecomment-2081352450
/*
async function mkDist() {
	try { await promises.mkdir('./dist') } catch (e) { if (e.code !== 'EEXIST') throw e }
}

function copy() {
	return src([ `${ASSETS_DIR}**`, `!${ASSETS_DIR}/**/*.{ts,tsx}`, `${ASSETS_DIR}**/*.d.ts`, ]).pipe(dest('./dist/'))
}

exports.copyAssets = series(mkDist, copy)
*/