# Circuit drawing with output="latex" needs a LaTeX installation (pdflatex),
# which Binder, Code Engine and most local kernels do not have; Qiskit then
# stops the cell with MissingOptionalLibraryError. Say so and draw the circuit
# with matplotlib instead, so the rest of the page still runs. "latex_source"
# needs no LaTeX and is left alone. Runs on every kernel, in every mode.
def _dq_latex_fallback():
    import shutil
    if shutil.which("pdflatex"):
        return
    try:
        import qiskit.visualization as vis
    except ImportError:
        return
    if getattr(vis.circuit_drawer, "_dq_latex", False):
        return
    drawer = vis.circuit_drawer

    def circuit_drawer(circuit, *args, **kwargs):
        if kwargs.get("output") == "latex":
            print("[doQumentation] LaTeX circuit drawing needs a LaTeX installation (pdflatex), "
                  "which this environment does not have. Drawing with matplotlib (output=\"mpl\") instead.")
            kwargs["output"] = "mpl"
        return drawer(circuit, *args, **kwargs)

    circuit_drawer._dq_latex = True
    circuit_drawer.__doc__ = drawer.__doc__
    vis.circuit_drawer = circuit_drawer


_dq_latex_fallback()
del _dq_latex_fallback
