from types import SimpleNamespace

import pytest

import pixlift.errors as errors


def test_format_error_appends_tail_when_present():
    msg = errors.format_error("Failed", "line1\nline2")
    assert msg == "Failed:\nline1\nline2"


def test_format_error_no_tail_when_stderr_empty():
    assert errors.format_error("Failed", "") == "Failed"
    assert errors.format_error("Failed", None) == "Failed"


def test_format_error_truncates_to_last_800_chars():
    stderr = "x" * 1000 + "END"
    msg = errors.format_error("Failed", stderr)
    tail = msg.split(":\n", 1)[1]
    assert len(tail) == 800
    assert tail.endswith("END")


def test_run_ffmpeg_returns_result_on_success(monkeypatch):
    fake_result = SimpleNamespace(returncode=0, stderr="")
    monkeypatch.setattr(errors, "run_hidden", lambda args: fake_result)
    assert errors.run_ffmpeg(["ffmpeg"], "Failed") is fake_result


def test_run_ffmpeg_raises_pipeline_error_on_failure(monkeypatch):
    fake_result = SimpleNamespace(returncode=1, stderr="boom")
    monkeypatch.setattr(errors, "run_hidden", lambda args: fake_result)
    with pytest.raises(errors.PipelineError, match="Merge failed:\nboom"):
        errors.run_ffmpeg(["ffmpeg"], "Merge failed")
