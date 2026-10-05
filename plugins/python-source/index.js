/**
 * Bundles *.py files as plain strings, so the kernel patches in src/kernel/
 * are real Python files: the site imports them and
 * scripts/check-simulator-mode.py runs the same files in CI.
 */
module.exports = function pythonSourcePlugin() {
  return {
    name: 'python-source',
    configureWebpack() {
      return {module: {rules: [{test: /\.py$/, type: 'asset/source'}]}};
    },
  };
};
