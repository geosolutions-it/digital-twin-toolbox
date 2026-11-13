import logging
import subprocess

import pytest

from app.worker.common.utils import run_subprocess

LOGGER = "app.worker.common.utils"


def lines(caplog):
    return [r.getMessage() for r in caplog.records if r.name == LOGGER]


def sh(script, **kwargs):
    return run_subprocess(["sh", "-c", script], **kwargs)


def test_streams_both_streams_and_returns_captured_output(caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    result = sh("echo out1; echo err1 >&2; echo out2", capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout == "out1\nout2\n"
    assert result.stderr == "err1\n"
    assert sorted(lines(caplog)) == ["err1", "out1", "out2"]


def test_parsed_stdout_is_returned_but_not_logged(caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    result = sh(
        "echo '{\"a\": 1}'; echo warn >&2", capture_output=True, log_stdout=False
    )
    assert result.stdout == b'{"a": 1}\n'
    assert lines(caplog) == ["warn"]


def test_without_capture_returns_no_output(caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    result = sh("echo hi")
    assert result.stdout is None and result.stderr is None
    assert lines(caplog) == ["hi"]


def test_progress_redraws_and_blank_lines_split(caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    sh(r"printf '10%%\r50%%\r100%%\n\n  \ndone\n'")
    assert lines(caplog) == ["10%", "50%", "100%", "done"]


def test_stage_of_marks_matching_lines(caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    sh(
        "echo plain; echo step 1",
        stage_of=lambda line: line.upper() if line.startswith("step") else None,
    )
    stages = [
        (r.getMessage(), getattr(r, "stage", None))
        for r in caplog.records
        if r.name == LOGGER
    ]
    assert stages == [("plain", None), ("step 1", "STEP 1")]


def test_check_raises_with_output():
    with pytest.raises(subprocess.CalledProcessError) as error:
        sh("echo bad >&2; exit 3", check=True, capture_output=True, text=True)
    assert error.value.returncode == 3
    assert error.value.stderr == "bad\n"


def test_nonzero_exit_without_check_returns_code():
    assert sh("exit 2").returncode == 2
