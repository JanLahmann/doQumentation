# Old import paths a package on PyPI still uses after Qiskit removed them.
# qiskit-ibm-transpiler 0.18 (the latest release) imports
# qiskit.synthesis.linear.linear_matrix_utils, which Qiskit 2.5 removed; the
# functions it needs are still exported by qiskit.synthesis.linear. Map the old
# module name to that package, so the AI transpiler pages run. Costs nothing
# until something imports one of these names. Runs on every kernel, in every mode.
# Also: progress bars as text (end of file).
def _dq_import_compat():
    import importlib
    import importlib.abc
    import importlib.util
    import sys

    aliases = {
        "qiskit.synthesis.linear.linear_matrix_utils": "qiskit.synthesis.linear",
    }
    if any(getattr(f, "_dq_import_compat", False) for f in sys.meta_path):
        return

    class _Alias(importlib.abc.MetaPathFinder, importlib.abc.Loader):
        _dq_import_compat = True

        def find_spec(self, name, path=None, target=None):
            if name not in aliases:
                return None
            # Only where the old module is really gone.
            sys.meta_path.remove(self)
            try:
                if importlib.util.find_spec(name) is not None:
                    return None
            except ImportError:
                pass
            finally:
                sys.meta_path.insert(0, self)
            return importlib.util.spec_from_loader(name, self)

        def create_module(self, spec):
            return importlib.import_module(aliases[spec.name])

        def exec_module(self, module):
            pass

    sys.meta_path.insert(0, _Alias())


_dq_import_compat()
del _dq_import_compat


# tqdm.auto picks the ipywidgets progress bar when ipywidgets is installed,
# but the page's widget manager cannot draw it ("Class HTMLStyleModel not
# found"), so a download's progress (e.g. the AI transpiler's models) showed
# nothing and logged errors. Use the text bar, which every page shows.
def _dq_text_progress_bars():
    try:
        import tqdm.auto
        import tqdm.autonotebook
        import tqdm.std
    except ImportError:
        return
    for mod in (tqdm.auto, tqdm.autonotebook):
        mod.tqdm = tqdm.std.tqdm
        mod.trange = tqdm.std.trange


_dq_text_progress_bars()
del _dq_text_progress_bars
