// Runtime settings for a self-hosted container. The site ships this empty
// default; scripts/docker-entrypoint.sh serves a generated one instead
// ({selfHosted: true, labEnabled: <LAB_ENABLED>}). Read by src/config/jupyter.ts.
// Never set selfHosted here: the public site would then look for Jupyter on
// its own origin.
window.__DOQ_RUNTIME__ = window.__DOQ_RUNTIME__ || {};
