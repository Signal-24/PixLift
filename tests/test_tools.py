import os

import pixlift.tools as tools


def test_first_existing_returns_none_when_nothing_matches(tmp_path):
    missing = str(tmp_path / "does_not_exist.exe")
    assert tools._first_existing([None, "", missing]) is None


def test_first_existing_returns_first_real_file(tmp_path):
    real = tmp_path / "real.exe"
    real.write_text("stub")
    missing = str(tmp_path / "missing.exe")
    assert tools._first_existing([missing, str(real)]) == os.path.abspath(str(real))


def test_resolve_ffmpeg_honors_env_var(tmp_path, monkeypatch):
    fake_ffmpeg = tmp_path / "ffmpeg.exe"
    fake_ffmpeg.write_text("stub")
    monkeypatch.setenv("PIXLIFT_FFMPEG", str(fake_ffmpeg))
    assert tools.resolve_ffmpeg() == os.path.abspath(str(fake_ffmpeg))


def test_resolve_realesrgan_honors_env_var(tmp_path, monkeypatch):
    fake_exe = tmp_path / "realesrgan-ncnn-vulkan.exe"
    fake_exe.write_text("stub")
    monkeypatch.setenv("PIXLIFT_REALESRGAN", str(fake_exe))
    assert tools.resolve_realesrgan() == os.path.abspath(str(fake_exe))


def test_check_tools_available_reports_missing_tools(monkeypatch):
    monkeypatch.setattr(tools, "resolve_realesrgan", lambda: None)
    monkeypatch.setattr(tools, "resolve_ffmpeg", lambda: None)
    monkeypatch.setattr(tools, "resolve_ffprobe", lambda: None)
    missing = tools.check_tools_available()
    assert len(missing) == 3
    assert any("realesrgan" in label for label in missing)
    assert any("ffmpeg" in label for label in missing)
    assert any("ffprobe" in label for label in missing)


def test_check_tools_available_empty_when_all_found(tmp_path, monkeypatch):
    fake = tmp_path / "tool.exe"
    fake.write_text("stub")
    monkeypatch.setattr(tools, "resolve_realesrgan", lambda: str(fake))
    monkeypatch.setattr(tools, "resolve_ffmpeg", lambda: str(fake))
    monkeypatch.setattr(tools, "resolve_ffprobe", lambda: str(fake))
    assert tools.check_tools_available() == []
