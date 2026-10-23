"""Test-host-only workaround for virtual PID vs shared /proc namespace.

Not an application patch. Keep real psutil affinity queries on the correct PID.
"""
import os,sys
if sys.platform=='linux':
    try:
        host_pid=int(os.readlink('/proc/self'))
        if host_pid!=os.getpid():
            import psutil
            _OriginalProcess=psutil.Process
            class Process(_OriginalProcess):
                def __init__(self,pid=None):
                    self._virtual_current = pid is None
                    super().__init__(int(os.readlink('/proc/self')) if pid is None else pid)
                def cpu_affinity(self, cpus=None):
                    if self._virtual_current:
                        if cpus is not None:os.sched_setaffinity(0,cpus)
                        return sorted(os.sched_getaffinity(0))
                    return super().cpu_affinity(cpus)
            psutil.Process=Process
    except (ImportError,OSError,ValueError):
        pass
