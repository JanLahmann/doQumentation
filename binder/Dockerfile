FROM quay.io/jupyter/base-notebook:python-3.12
# Install from requirements file (single source of truth for all Qiskit deps)
COPY --chown=1000:100 binder/jupyter-requirements.txt /tmp/jupyter-requirements.txt
RUN pip install --no-cache-dir --no-compile -r /tmp/jupyter-requirements.txt && \
    rm /tmp/jupyter-requirements.txt && \
    find ${CONDA_DIR}/lib -type d -name tests -exec rm -rf {} + 2>/dev/null || true && \
    find ${CONDA_DIR}/lib -type d -name test  -exec rm -rf {} + 2>/dev/null || true && \
    find ${CONDA_DIR}/lib -name '*.pyc' -delete 2>/dev/null || true && \
    find ${CONDA_DIR}/lib -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find ${CONDA_DIR}/lib -name '*.so' -exec strip --strip-unneeded {} + 2>/dev/null || true && \
    rm -rf ${CONDA_DIR}/share/{doc,man,gtk-doc} 2>/dev/null || true
# repo2docker does not auto-copy files when using binder/Dockerfile — do it explicitly
COPY --chown=1000:100 . /home/jovyan/
WORKDIR /home/jovyan
