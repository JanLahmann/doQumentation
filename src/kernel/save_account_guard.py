# Kernel-side guard for QiskitRuntimeService.save_account(), run on every
# kernel in every execution mode (src/kernel/index.ts). Doc pages ship
# save_account() cells with placeholder tokens such as "<your-api-key>";
# running one unguarded writes the placeholder to ~/.qiskit with
# overwrite=True, which on a shared Workshop container hits everyone (#966).
#
# A placeholder is recognised by shape, not by a list of spellings: IBM Cloud
# API keys are 44 characters of [A-Za-z0-9_-] and legacy IBM Quantum tokens
# are 128 hex characters, so anything that is not 32+ such characters, or that
# spells out "your", "token" or "api key" (your_qiskit_functions_catalog_token),
# is a placeholder. scripts/check-simulator-mode.py asserts that every
# token="..." in docs/ is classified as one.
import re as _dq_re
from qiskit_ibm_runtime import QiskitRuntimeService as _DQ_QRS


def _dq_is_placeholder(token, instance=None):
    token = str(token or "")
    if not _dq_re.fullmatch(r"[A-Za-z0-9_\-]{32,}", token):
        return True
    if _dq_re.search(r"your|token|api[-_]?key", token, _dq_re.I):
        return True
    return bool(instance) and ("<" in str(instance) or ">" in str(instance))


if not getattr(_DQ_QRS.save_account, "_dq_guard", False):
    _DQ_real_save_account = _DQ_QRS.save_account

    def _dq_guarded_save_account(*args, **kwargs):
        token = kwargs.get("token", args[0] if args else None)
        if _dq_is_placeholder(token, kwargs.get("instance")):
            print("[doQumentation] save_account() skipped: the token is a placeholder, "
                  "so nothing was saved. Paste your real API key into the cell, "
                  "or set it in Settings → IBM Quantum.")
            return None
        return _DQ_real_save_account(*args, **kwargs)

    _dq_guarded_save_account._dq_guard = True
    _dq_guarded_save_account._dq_real = _DQ_real_save_account  # credentials from Settings bypass the guard
    _DQ_QRS.save_account = staticmethod(_dq_guarded_save_account)
