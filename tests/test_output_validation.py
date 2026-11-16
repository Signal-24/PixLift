"""Motor ciktisi dogrulama ve otomatik yeniden deneme (GPU/ffmpeg gerektirmez)."""

import os
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication

import pixlift.media as media
import pixlift.worker as worker_mod
from pixlift.errors import EngineOutputError, PipelineError
from pixlift.settings import STRINGS

CELLS = media.SAMPLE_SIZE * media.SAMPLE_SIZE


def flat(value):
    return bytes([value]) * CELLS


def textured(base=100):
    return bytes(base + (i * 7) % 100 for i in range(CELLS))


# --- saf mantik ---------------------------------------------------------------


def test_sample_stats():
    mean, std = media.sample_stats(flat(10))
    assert mean == 10 and std == 0
    mean, std = media.sample_stats(bytes([0, 100] * (CELLS // 2)))
    assert mean == 50 and std == pytest.approx(50)


def test_looks_corrupt_flags_black_output():
    assert media.looks_corrupt(textured(), flat(0)) is True


def test_looks_corrupt_flags_solid_green_or_gray_output():
    assert media.looks_corrupt(textured(), flat(150)) is True


def test_looks_corrupt_flags_partly_black_output():
    good = textured()
    broken = bytes(0 if i < CELLS * 0.05 else v for i, v in enumerate(good))
    assert media.looks_corrupt(good, broken) is True


def test_looks_corrupt_accepts_faithful_output():
    original = textured()
    upscaled = bytes(min(255, v + 3) for v in original)  # kucuk renk farki normaldir
    assert media.looks_corrupt(original, upscaled) is False


def test_looks_corrupt_accepts_genuinely_flat_image():
    assert media.looks_corrupt(flat(0), flat(0)) is False
    assert media.looks_corrupt(flat(200), flat(200)) is False


def test_looks_corrupt_unknown_samples_do_not_alarm():
    assert media.looks_corrupt(None, flat(0)) is False
    assert media.looks_corrupt(textured(), None) is False


def test_engine_stderr_problem():
    assert media.engine_stderr_problem("decode image C:\\a.png failed") == "decode_failed"
    assert media.engine_stderr_problem("vkQueueSubmit failed -4") == "gpu_error"
    assert media.engine_stderr_problem("vkAllocateMemory failed") == "gpu_error"
    assert media.engine_stderr_problem("out of device memory") == "gpu_error"
    assert media.engine_stderr_problem("0.00%\n25.00%\n100.00%") is None
    assert media.engine_stderr_problem("") is None
    assert media.engine_stderr_problem(None) is None


@pytest.fixture
def fake_samples(monkeypatch):
    """image_sample: dosya icerigine gore sahte ornek dondurur."""
    def sample(path):
        if not os.path.isfile(path):
            return None
        data = open(path, "rb").read()
        if data == b"BLACK":
            return flat(0)
        if data == b"JUNK":
            return None
        return textured()

    monkeypatch.setattr(media, "image_sample", sample)
    monkeypatch.setattr(worker_mod, "image_sample", sample)
    return sample


def _files(tmp_path, out_bytes):
    src = tmp_path / "in.png"
    src.write_bytes(b"GOOD")
    out = tmp_path / "out.png"
    if out_bytes is not None:
        out.write_bytes(out_bytes)
    return str(src), str(out)


@pytest.mark.parametrize(
    "out_bytes, returncode, stderr, expected",
    [
        (b"GOOD", 0, "", None),
        (b"GOOD", 1, "", "exit_code"),
        (None, 0, "", "no_output"),
        (b"", 0, "", "no_output"),
        (b"JUNK", 0, "", "unreadable"),
        (b"BLACK", 0, "", "blank_output"),
        (b"GOOD", 0, "vkQueueSubmit failed -4", "gpu_error"),
        (None, 0, "decode image x failed", "decode_failed"),
    ],
)
def test_output_problem(tmp_path, fake_samples, out_bytes, returncode, stderr, expected):
    src, out = _files(tmp_path, out_bytes)
    assert media.output_problem(src, out, returncode, stderr) == expected


# --- fotograf akisi: siyah cikti -> daha kucuk tile ile yeniden deneme -----------------


class FakeEngine:
    """subprocess.Popen yerine gecer; tile degerine gore davranir."""

    calls = []
    behavior = {}  # tile -> ("BLACK" | "GOOD" | "NOTHING", stderr_text)

    def __init__(self, cmd, **kwargs):
        args = dict(zip(cmd[1::2], cmd[2::2]))
        tile = int(args["-t"])
        FakeEngine.calls.append(tile)
        kind, stderr_text = FakeEngine.behavior.get(tile, ("GOOD", ""))
        if kind != "NOTHING":
            with open(args["-o"], "wb") as f:
                f.write(kind.encode())
        kwargs["stderr"].write(stderr_text)
        kwargs["stderr"].flush()
        self.returncode = 0

    def poll(self):
        return 0

    def wait(self, timeout=None):
        return 0

    def kill(self):
        pass


@pytest.fixture
def photo_job(tmp_path, monkeypatch, fake_samples):
    QCoreApplication.instance() or QCoreApplication([])
    FakeEngine.calls = []
    FakeEngine.behavior = {}
    monkeypatch.setattr(worker_mod.subprocess, "Popen", FakeEngine)
    monkeypatch.setattr(worker_mod.tools, "REALESRGAN_EXE", str(tmp_path / "realesrgan.exe"))
    monkeypatch.setattr(
        worker_mod, "probe_image",
        lambda path: {"width": 100, "height": 100, "frame_count": 1, "fps": 0},
    )
    src = tmp_path / "foto.png"
    src.write_bytes(b"GOOD")

    def run():
        w = worker_mod.UpscaleWorker(str(src), 4, "fast")
        result = SimpleNamespace(ok=None, failed=None, status=[])
        w.finished_ok.connect(lambda p: setattr(result, "ok", p))
        w.failed.connect(lambda m: setattr(result, "failed", m))
        w.status.connect(result.status.append)
        w.run()
        result.output = str(tmp_path / "foto_PixLift_4x.png")
        return result

    return run


def test_photo_black_output_is_retried_with_smaller_tile(photo_job):
    FakeEngine.behavior = {0: ("BLACK", "")}  # otomatik tile siyah uretir, 128 duzgun
    result = photo_job()
    assert result.failed is None
    assert FakeEngine.calls == [0, 128]
    assert result.ok == result.output
    with open(result.output, "rb") as f:
        assert f.read() == b"GOOD"  # siyah dosya degil, dogrusu teslim edildi
    assert any("128" in s for s in result.status)  # kullaniciya yeniden deneme bildirildi


def test_photo_all_black_fails_clearly_and_leaves_no_output(photo_job):
    FakeEngine.behavior = {t: ("BLACK", "") for t in media.TILE_FALLBACKS}
    result = photo_job()
    assert result.ok is None
    assert FakeEngine.calls == list(media.TILE_FALLBACKS)
    assert STRINGS["tr"]["reason_blank_output"] in result.failed
    assert not os.path.exists(result.output)  # bozuk dosya klasore birakilmaz


def test_photo_gpu_error_in_stderr_triggers_retry(photo_job):
    FakeEngine.behavior = {0: ("GOOD", "vkQueueSubmit failed -4")}
    result = photo_job()
    assert FakeEngine.calls == [0, 128]
    assert result.ok == result.output


def test_photo_unreadable_input_is_not_retried(photo_job):
    FakeEngine.behavior = {0: ("NOTHING", "decode image foto.png failed")}
    result = photo_job()
    assert FakeEngine.calls == [0]  # yeniden denemek isi cozmez
    assert STRINGS["tr"]["reason_decode_failed"] in result.failed


def test_photo_good_output_runs_once(photo_job):
    result = photo_job()
    assert FakeEngine.calls == [0]
    assert result.ok == result.output


# --- video/GIF: kare klasoru yeniden deneme ----------------------------------------


def _frame_worker(monkeypatch, tmp_path, outcomes):
    QCoreApplication.instance() or QCoreApplication([])
    frames_in = tmp_path / "in"
    frames_out = tmp_path / "out"
    frames_in.mkdir()
    frames_out.mkdir()
    w = worker_mod.UpscaleWorker("clip.mp4", 2, "fast")
    seen = []

    def fake_run(fin, fout, model, scale, stall, total, tile=0):
        seen.append((tile, sorted(os.listdir(fout))))
        (frames_out / "frame_00001.png").write_bytes(b"x")  # bu denemenin ciktisi
        outcome = outcomes.get(tile, True)
        if isinstance(outcome, str):
            raise EngineOutputError(outcome, "detail")
        return outcome

    w._run_realesrgan_frames = fake_run
    logs = []
    w.status.connect(logs.append)
    return w, str(frames_in), str(frames_out), seen, logs


def test_frames_black_first_attempt_cleans_and_retries(monkeypatch, tmp_path):
    w, fin, fout, seen, logs = _frame_worker(monkeypatch, tmp_path, {0: "blank_output"})
    assert w._upscale_frames_with_fallback(fin, fout, "m", 2, 100, 10) is True
    assert [t for t, _ in seen] == [0, 128]
    assert seen[1][1] == []  # onceki denemenin kareleri temizlenmis
    assert any("128" in s for s in logs)


def test_frames_all_attempts_fail_raises_clear_error(monkeypatch, tmp_path):
    outcomes = {t: "missing_frames" for t in media.TILE_FALLBACKS}
    w, fin, fout, seen, _ = _frame_worker(monkeypatch, tmp_path, outcomes)
    with pytest.raises(PipelineError) as info:
        w._upscale_frames_with_fallback(fin, fout, "m", 2, 100, 10)
    assert [t for t, _ in seen] == list(media.TILE_FALLBACKS)
    assert STRINGS["tr"]["reason_missing_frames"] in str(info.value)


def test_frames_decode_failure_is_not_retried(monkeypatch, tmp_path):
    w, fin, fout, seen, _ = _frame_worker(monkeypatch, tmp_path, {0: "decode_failed"})
    with pytest.raises(PipelineError):
        w._upscale_frames_with_fallback(fin, fout, "m", 2, 100, 10)
    assert [t for t, _ in seen] == [0]


def test_frames_cancel_returns_false(monkeypatch, tmp_path):
    w, fin, fout, seen, _ = _frame_worker(monkeypatch, tmp_path, {0: False})
    assert w._upscale_frames_with_fallback(fin, fout, "m", 2, 100, 10) is False
    assert [t for t, _ in seen] == [0]


def test_all_reason_strings_exist_in_both_languages():
    reasons = ["exit_code", "decode_failed", "gpu_error", "no_output",
               "unreadable", "blank_output", "missing_frames"]
    for lang in ("tr", "en"):
        for key in ["w_retry_tile", "w_output_bad"] + [f"reason_{r}" for r in reasons]:
            assert key in STRINGS[lang], f"{lang}: {key}"
