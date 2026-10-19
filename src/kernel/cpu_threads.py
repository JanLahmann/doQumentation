# Thread cap for kernels on a CPU quota (src/kernel/index.ts runs this in
# every mode, before the page's cells).
# A Binder pod reports the host's CPUs (48 on mybinder.org) but gets one CPU
# of quota (cgroup cpu.max). Aer, OpenBLAS and OpenMP each start a thread per
# reported CPU, and those threads fight over the one CPU: guides/hello-world's
# Estimator took 100 s there instead of 1.3 s. Cap them at the quota. A
# notebook that sets max_parallel_threads itself keeps its own value.
def _dq_cap_threads():
    import os

    def quota():
        try:  # cgroup v2: "<quota> <period>" or "max <period>"
            q, p = open("/sys/fs/cgroup/cpu.max").read().split()[:2]
            return None if q == "max" else max(1, -(-int(q) // int(p)))
        except (OSError, ValueError):
            pass
        try:  # cgroup v1
            q = int(open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read())
            p = int(open("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read())
            return max(1, -(-q // p)) if q > 0 else None
        except (OSError, ValueError):
            return None

    n = quota()
    if not n or n >= (os.cpu_count() or 1):
        return
    try:
        from qiskit_aer import AerSimulator
    except ImportError:
        AerSimulator = None
    try:  # after the Aer import, which loads numpy's OpenBLAS and OpenMP
        from threadpoolctl import threadpool_limits
        threadpool_limits(n)
    except Exception:
        pass
    if AerSimulator is None or getattr(AerSimulator.__init__, "_dq_threads", False):
        return
    init = AerSimulator.__init__

    def capped_init(self, *args, **options):
        options.setdefault("max_parallel_threads", n)
        init(self, *args, **options)

    capped_init._dq_threads = True
    AerSimulator.__init__ = capped_init


_dq_cap_threads()
del _dq_cap_threads
