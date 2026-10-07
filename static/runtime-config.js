// Runtime settings for a self-hosted container. The site ships this empty
// default; scripts/docker-entrypoint.sh serves a generated one instead
// (LAB_ENABLED=false -> {labEnabled: false}). Read by src/config/jupyter.ts.
window.__DOQ_RUNTIME__ = window.__DOQ_RUNTIME__ || {};
