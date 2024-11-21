/* gulpfile.js */

const gulp = require('gulp');
const webpack = require('webpack-stream');
const uswds = require('@uswds/compile');
const TerserPlugin = require('terser-webpack-plugin');

const ASSETS_DIR = './registrar/assets/';
const JS_BUNDLE_DEST = ASSETS_DIR + 'js';
const JS_SOURCES = [
    { src: ASSETS_DIR + 'src/js/getgov/*.js', output: 'getgov.min.js' },
    { src: ASSETS_DIR + 'src/js/getgov-admin/*.js', output: 'getgov-admin.min.js' },
];

/**
 * USWDS version
 * Set the version of USWDS you're using (2 or 3)
 */
uswds.settings.version = 3;

/**
 * Path settings
 * Set as many as you need
 */
uswds.paths.dist.css = ASSETS_DIR + 'css';
uswds.paths.dist.sass = ASSETS_DIR + 'sass';
uswds.paths.dist.theme = ASSETS_DIR + 'src/sass/_theme';
uswds.paths.dist.fonts = ASSETS_DIR + 'fonts';
uswds.paths.dist.js = ASSETS_DIR + 'js';
uswds.paths.dist.img = ASSETS_DIR + 'img';

/**
 * Function: Create Bundling Task
 */
function createBundleTask(source, output) {
    return () =>
        gulp
            .src(source)
            .pipe(
                webpack({
                    mode: 'production', // Use 'development' if you want less minification during debugging
                    devtool: 'source-map', // Enable source map generation
                    optimization: {
                        minimize: true,
                        minimizer: [
                            new TerserPlugin({
                                extractComments: false, // Prevents generating .LICENSE.txt
                            }),
                        ],
                    },
                    output: { filename: output },
                    module: {
                        rules: [
                            {
                                test: /\.js$/,
                                exclude: /node_modules/,
                                use: {
                                    loader: 'babel-loader',
                                    options: { presets: ['@babel/preset-env'] },
                                },
                            },
                        ],
                    },
                })
            )
            .pipe(gulp.dest(JS_BUNDLE_DEST));
}

// Create tasks for JavaScript sources
JS_SOURCES.forEach(({ src, output }, index) => {
    const taskName = `bundle-js-${index}`;
    gulp.task(taskName, createBundleTask(src, output));
});

/**
 * Watch for changes in JavaScript modules
 */
gulp.task('watch-js', () => {
    JS_SOURCES.forEach(({ src }, index) => {
        gulp.watch(src, gulp.series(`bundle-js-${index}`));
    });
});

/**
 * Combine all watch tasks
 */
gulp.task('watch', gulp.parallel('watch-js', uswds.watch));

/**
 * Exports
 * Add as many as you need
 * Some tasks combine USWDS compilation and JavaScript precompilation.
 */
exports.default = gulp.series(uswds.compile, ...JS_SOURCES.map((_, i) => `bundle-js-${i}`));
exports.init = uswds.init;
exports.compile = gulp.series(uswds.compile, ...JS_SOURCES.map((_, i) => `bundle-js-${i}`));
exports.watch = uswds.watch;
exports.watchAll = gulp.parallel('watch');
exports.copyAssets = uswds.copyAssets
exports.updateUswds = uswds.updateUswds
