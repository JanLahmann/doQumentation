FROM quay.io/jupyter/base-notebook:python-3.12
RUN pip install --no-cache-dir --no-compile \
    "qiskit[visualization]~=2.3.0" \
    "qiskit-aer~=0.17" \
    "qiskit-ibm-runtime~=0.43.1" \
    qiskit-ibm-catalog \
    qiskit-ibm-transpiler \
    qiskit-addon-cutting \
    pylatexenc \
    scikit-learn \
    networkx && \
    find ${CONDA_DIR}/lib -type d -name tests -exec rm -rf {} + 2>/dev/null || true && \
    find ${CONDA_DIR}/lib -type d -name test  -exec rm -rf {} + 2>/dev/null || true && \
    find ${CONDA_DIR}/lib -name '*.pyc' -delete 2>/dev/null || true && \
    find ${CONDA_DIR}/lib -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find ${CONDA_DIR}/lib -name '*.so' -exec strip --strip-unneeded {} + 2>/dev/null || true && \
    rm -rf ${CONDA_DIR}/share/{doc,man,gtk-doc} 2>/dev/null || true
COPY --chown=1000:100 . /home/jovyan/
WORKDIR /home/jovyan
