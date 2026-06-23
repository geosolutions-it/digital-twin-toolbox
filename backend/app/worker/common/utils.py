import os
import shutil
import signal
import ctypes
import threading
import subprocess
from app.core.config import settings


try:
    _libc = ctypes.CDLL("libc.so.6", use_errno=True)
except OSError:
    _libc = None


def _set_pdeathsig():
    # PR_SET_PDEATHSIG=1: kernel SIGKILLs this child if the worker dies (no orphans on revoke).
    if _libc is not None:
        _libc.prctl(1, signal.SIGKILL)


def run_subprocess(cmd, check=False, capture_output=False, text=False):
    """subprocess.run that kills the child's whole process group on revoke(terminate=True),
    so native children (incl micromamba -> opensfm) don't outlive the task."""
    pipe = subprocess.PIPE if capture_output else None
    proc = subprocess.Popen(
        cmd, stdout=pipe, stderr=pipe, text=text,
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


def get_asset_upload_path(pathname):
    return os.path.join(settings.ASSETS_DATA, "upload", pathname)


def get_asset_table_name(asset_id):
    id = f"{asset_id}".replace('-', '_')
    return f'asset_{id}'


def get_pipeline_table_name(pipeline_id):
    id = f"{pipeline_id}".replace('-', '_')
    return f'pipeline_{id}'


def get_process_dir(pipeline_id):
    """Path of the shared per-pipeline process dir (no side effects, unlike setup_output_directory)."""
    return os.path.join(settings.ASSETS_DATA, "output", f"{pipeline_id}", "process")


def setup_output_directory(pipeline_id):
    relative_output_path = os.path.join("output", f"{pipeline_id}")
    output_path = os.path.join(settings.ASSETS_DATA, relative_output_path)

    try:
        for filename in os.listdir(output_path):
            if filename != 'process':
                shutil.rmtree(os.path.join(output_path, filename))
    except Exception:
        pass

    os.makedirs(output_path, exist_ok=True)

    return {
        'relative_output_path': relative_output_path,
        'output_path': output_path,
        'output_path_3dtiles': os.path.join(output_path, 'tiles'),
        'output_path_3dtiles_zip': os.path.join(output_path, 'download'),
        'output_tileset': os.path.join(settings.API_V1_STR, relative_output_path, 'tiles', 'tileset.json'),
        'output_tileset_zip': os.path.join(settings.API_V1_STR, relative_output_path, 'download.zip'),
    }
