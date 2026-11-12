import os
import signal
import ctypes
import threading
import subprocess


try:
    _libc = ctypes.CDLL("libc.so.6", use_errno=True)
except OSError:
    _libc = None


def _set_pdeathsig():
    # PR_SET_PDEATHSIG=1: kernel SIGKILLs this child if the worker dies (no orphans on revoke).
    if _libc is not None:
        _libc.prctl(1, signal.SIGKILL)


def run_subprocess(cmd, check=False, capture_output=False, text=False, cwd=None):
    """subprocess.run that kills the child's whole process group on revoke(terminate=True),
    so native children (incl micromamba -> opensfm) don't outlive the task."""
    pipe = subprocess.PIPE if capture_output else None
    proc = subprocess.Popen(
        cmd, stdout=pipe, stderr=pipe, text=text, cwd=cwd,
        start_new_session=True, preexec_fn=_set_pdeathsig,
    )
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        pgid = None

    def _kill_group(signum, frame):
        if pgid is not None:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        raise SystemExit(128 + signum)

    prev_handler = None
    on_main_thread = threading.current_thread() is threading.main_thread()
    if on_main_thread:
        try:
            prev_handler = signal.getsignal(signal.SIGTERM)
            signal.signal(signal.SIGTERM, _kill_group)
        except (ValueError, OSError):
            on_main_thread = False

    try:
        out, err = proc.communicate()
    finally:
        if on_main_thread:
            signal.signal(signal.SIGTERM, prev_handler)

    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd, output=out, stderr=err)
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout=out, stderr=err)

