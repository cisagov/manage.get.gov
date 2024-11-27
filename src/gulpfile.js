/* gulpfile.js */

// We need a hook into gulp for the JS jobs definitions
const gulp = require('gulp');
// For bundling
const webpack = require('webpack-stream');
// Out-of-the-box uswds compiler
const uswds = require('@uswds/compile');
// For minimizing and optimizing
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
 * 
 * This function generates a Gulp task for bundling JavaScript files. It accepts a source file pattern
 * and an output filename, then processes the files using Webpack for tasks like transpilation, bundling, 
 * and optimization. The resulting task performs the following:
 * 
 * 1. Reads the JavaScript source files specified by the `source` parameter.
 * 2. Transforms the JavaScript using Webpack:
 *    - Runs in "production" mode by default for optimizations (use "development" mode for easier debugging).
 *    - Generates a source map for better debugging experience, linking the output to the original source.
 *    - Minifies the code using TerserPlugin while suppressing the generation of `.LICENSE.txt` files.
 *    - Processes the JavaScript with Babel to ensure compatibility with older browsers by using the `@babel/preset-env`.
 * 3. Outputs the bundled and optimized JavaScript to the specified destination folder.
 * 
 * Parameters:
 * - `source`: A glob pattern or file path specifying the input JavaScript files.
 * - `output`: The filename for the generated JavaScript bundle.
 * 
 * Returns:
 * - A function that can be executed as a Gulp task.
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
