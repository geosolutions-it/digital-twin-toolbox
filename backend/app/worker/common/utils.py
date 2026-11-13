import logging
import os
import signal
import ctypes
import threading
import subprocess

logger = logging.getLogger(__name__)

try:
    _libc = ctypes.CDLL("libc.so.6", use_errno=True)
except OSError:
    _libc = None


def _set_pdeathsig():
    # PR_SET_PDEATHSIG=1: kernel SIGKILLs this child if the worker dies (no orphans on revoke).
    if _libc is not None:
        _libc.prctl(1, signal.SIGKILL)


MAX_LINE = 2000


def _pump(stream, sink, forward, stage_of):
    for raw in iter(stream.readline, b""):
        if sink is not None:
            sink.append(raw)
        if forward:
            # progress bars redraw with \r
            for line in raw.replace(b"\r", b"\n").decode("utf-8", "replace").splitlines():
                if line.strip():
                    stage = stage_of(line) if stage_of else None
                    logger.info(line[:MAX_LINE], extra={"stage": stage[:255]} if stage else None)
    stream.close()


def run_subprocess(cmd, check=False, capture_output=False, text=False, cwd=None, log_stdout=True, stage_of=None):
    """subprocess.run that logs each output line as it arrives (stdout only with log_stdout) and kills the
    child's whole process group on revoke(terminate=True), so native children (incl micromamba -> opensfm)
    don't outlive the task. stage_of(line) may return a stage name for that line."""
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd,
        start_new_session=True, preexec_fn=_set_pdeathsig,
    )
    out, err = ([], []) if capture_output else (None, None)
    pumps = [
        threading.Thread(target=_pump, args=(proc.stdout, out, log_stdout, stage_of), daemon=True),
        threading.Thread(target=_pump, args=(proc.stderr, err, True, stage_of), daemon=True),
    ]
    for pump in pumps:
        pump.start()
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        pgid = None

    def _kill_group(signum, _frame):
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
        proc.wait()
        for pump in pumps:
            pump.join()
    finally:
        if on_main_thread:
            signal.signal(signal.SIGTERM, prev_handler)

    if capture_output:
        out, err = b"".join(out), b"".join(err)
        if text:
            out, err = out.decode("utf-8", "replace"), err.decode("utf-8", "replace")

    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd, output=out, stderr=err)
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout=out, stderr=err)

