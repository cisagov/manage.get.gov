/* gulpfile.js */

const uswds = require('@uswds/compile');

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
exports.updateUswds = uswds.updateUswds
                                                                                  