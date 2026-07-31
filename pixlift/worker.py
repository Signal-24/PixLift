"""Buyutme pipeline'i: kare cikarma/birlestirme, ses isleme, Real-ESRGAN calistirma."""

import os
import shutil
import subprocess
import tempfile
import time

from PySide6.QtCore import QThread, Signal

from . import tools
from .errors import PipelineError, format_error, run_ffmpeg
from .media import (
    BENCHMARKS,
    STALL_TIMEOUT_MIN_SECONDS,
    STALL_TIMEOUT_SECONDS,
    analyze_audio_gain,
    engine_scale_for,
    estimate_seconds_per_frame,
    format_duration,
    image_output_format,
    is_gif_file,
    is_image_file,
    needs_post_downscale,
    probe_image,
    probe_video,
    stall_timeout_for_job,
    target_size,
)
from .settings import STRINGS
from .tools import run_hidden


class UpscaleWorker(QThread):
    progress = Signal(int)
    status = Signal(str)
    finished_ok = Signal(str)
    failed = Signal(str)
    cancelled = Signal()
    warning = Signal(str)

    def __init__(self, input_path, scale, quality_key, audio_mode="auto", output_fps=None, strings=None):
        super().__init__()
        self.input_path = input_path
        self.scale = scale
        self.quality_key = quality_key
        # audio_mode: "off" | "auto" | "25" | "50" | "100"
        self.audio_mode = audio_mode
        self.output_fps = output_fps  # None = orijinal
        self.strings = strings or STRINGS["tr"]
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def t(self, key, **kwargs):
        template = self.strings.get(key, key)
        return template.format(**kwargs) if kwargs else template

    def log(self, message):
        self.status.emit(message)

    def _duration_units(self):
        return {"sec": self.t("unit_sec"), "min": self.t("unit_min"), "hr": self.t("unit_hr")}

    def _wait_realesrgan(self, proc, frames_out, total_frames, stall_limit, stderr_path):
        """Real-ESRGAN bitene kadar izle; kare ilerlemesi yoksa stall_limit sonra kes.

        stderr dosyaya yazilir (PIPE + okumamak Windows'ta sureci kilitleyebilir).
        """
        last_done = 0
        last_progress_time = time.time()
        while proc.poll() is None:
            if self._cancelled:
                proc.kill()
                return False
            done = len([f for f in os.listdir(frames_out) if f.endswith(".png")])
            if done != last_done:
                last_done = done
                last_progress_time = time.time()
            elif time.time() - last_progress_time > stall_limit:
                proc.kill()
                stderr_tail = ""
                try:
                    with open(stderr_path, "r", encoding="utf-8", errors="replace") as f:
                        stderr_tail = f.read()[-800:]
                except OSError:
                    pass
                detail = f"\n{stderr_tail}" if stderr_tail.strip() else ""
                raise PipelineError(
                    self.t("w_stall_video", done=done, stall=int(stall_limit)) + detail
                )
            pct = 5 + int(90 * done / max(total_frames, 1))
            self.progress.emit(min(pct, 95))
            time.sleep(0.5)
        return True

    def _run_realesrgan_frames(self, frames_in, frames_out, model, scale, stall_limit, total_frames):
        stderr_path = os.path.join(os.path.dirname(frames_out), "realesrgan_stderr.log")
        engine_scale = engine_scale_for(model, scale)
        with open(stderr_path, "w", encoding="utf-8", errors="replace") as stderr_file:
            proc = subprocess.Popen(
                [
                    tools.REALESRGAN_EXE,
                    "-i", frames_in,
                    "-o", frames_out,
                    "-n", model,
                    "-s", str(engine_scale),
                    "-t", "0",
                    "-f", "png",
                ],
                cwd=os.path.dirname(tools.REALESRGAN_EXE),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=stderr_file,
                creationflags=tools.NO_CREATE_WINDOW,
            )
            alive = self._wait_realesrgan(proc, frames_out, total_frames, stall_limit, stderr_path)

        if not alive:
            return False

        if proc.returncode != 0:
            stderr_tail = ""
            try:
                with open(stderr_path, "r", encoding="utf-8", errors="replace") as f:
                    stderr_tail = f.read()[-800:]
            except OSError:
                pass
            raise PipelineError(format_error(self.t("w_upscale_failed"), stderr_tail))
        return True

    def run(self):
        temp_dir = tempfile.mkdtemp(prefix="pixlift_")
        try:
            if is_image_file(self.input_path):
                self._run_image_pipeline()
            elif is_gif_file(self.input_path):
                self._run_gif_pipeline(temp_dir)
            else:
                self._run_pipeline(temp_dir)
            if self._cancelled:
                self.cancelled.emit()
        except PipelineError as e:
            if not self._cancelled:
                self.failed.emit(str(e))
        except Exception as e:  # noqa: BLE001 - kisisel arac, genel hata mesaji yeterli
            if not self._cancelled:
                self.failed.emit(self.t("w_unexpected_error", error=e))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _run_image_pipeline(self):
        info = probe_image(self.input_path)
        model = BENCHMARKS[self.quality_key]["model"]
        engine_scale = engine_scale_for(model, self.scale)
        post_downscale = needs_post_downscale(model, self.scale)
        # ETA: motor gercekten native olcekte calisiyorsa onu baz al
        estimated_total = max(
            estimate_seconds_per_frame(info, self.quality_key, engine_scale),
            1.0,
        )

        base, ext = os.path.splitext(self.input_path)
        out_ext = image_output_format(ext)
        output_path = f"{base}_PixLift_{self.scale}x.{out_ext}"
        work_path = output_path
        if post_downscale:
            work_path = os.path.join(
                tempfile.gettempdir(),
                f"pixlift_img_{os.getpid()}_x{engine_scale}.png",
            )

        scale_note = f"{engine_scale}x→{self.scale}x" if post_downscale else f"{self.scale}x"
        self.status.emit(self.t("w_upscaling_photo", model=model, scale_note=scale_note))
        self.progress.emit(5)

        start = time.time()
        stderr_path = os.path.join(tempfile.gettempdir(), f"pixlift_img_{os.getpid()}.log")
        with open(stderr_path, "w", encoding="utf-8", errors="replace") as stderr_file:
            proc = subprocess.Popen(
                [
                    tools.REALESRGAN_EXE,
                    "-i", self.input_path,
                    "-o", work_path,
                    "-n", model,
                    "-s", str(engine_scale),
                    "-t", "0",
                    "-f", "png" if post_downscale else out_ext,
                ],
                cwd=os.path.dirname(tools.REALESRGAN_EXE),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=stderr_file,
                creationflags=tools.NO_CREATE_WINDOW,
            )
            stall_limit = max(estimated_total * 4, STALL_TIMEOUT_SECONDS, STALL_TIMEOUT_MIN_SECONDS)
            while proc.poll() is None:
                if self._cancelled:
                    proc.kill()
                    return
                elapsed = time.time() - start
                if elapsed > stall_limit:
                    proc.kill()
                    raise PipelineError(self.t("w_stall_photo"))
                pct = 5 + int(90 * min(elapsed / estimated_total, 1.0))
                self.progress.emit(min(pct, 95))
                time.sleep(0.2)

        if proc.returncode != 0:
            stderr_tail = ""
            try:
                with open(stderr_path, "r", encoding="utf-8", errors="replace") as f:
                    stderr_tail = f.read()[-800:]
            except OSError:
                pass
            raise PipelineError(format_error(self.t("w_upscale_failed"), stderr_tail))

        if post_downscale:
            if self._cancelled:
                return
            self.status.emit(self.t("w_downscaling_photo", scale=self.scale))
            tw, th = target_size(info, self.scale)
            # Basarisiz olsa bile work_path her zaman temizlenmeli; bu yuzden
            # run_ffmpeg yerine burada dogrudan run_hidden kullaniliyor.
            result = run_hidden(
                [
                    tools.FFMPEG_EXE, "-y", "-i", work_path,
                    "-vf", f"scale={tw}:{th}:flags=lanczos",
                    output_path,
                ]
            )
            try:
                os.remove(work_path)
            except OSError:
                pass
            if result.returncode != 0:
                raise PipelineError(format_error(self.t("w_resize_failed"), result.stderr))

        self.progress.emit(100)
        self.finished_ok.emit(output_path)

    def _run_pipeline(self, temp_dir):
        info = probe_video(self.input_path)
        frames_in = os.path.join(temp_dir, "frames_in")
        frames_out = os.path.join(temp_dir, "frames_out")
        os.makedirs(frames_in, exist_ok=True)
        os.makedirs(frames_out, exist_ok=True)

        self.status.emit(self.t("w_extracting_frames"))
        self.progress.emit(1)
        run_ffmpeg(
            [
                tools.FFMPEG_EXE, "-y", "-i", self.input_path,
                "-qscale:v", "2",
                os.path.join(frames_in, "frame_%05d.png"),
            ],
            self.t("w_extract_frames_failed"),
        )
        if self._cancelled:
            return

        total_frames = len([f for f in os.listdir(frames_in) if f.endswith(".png")])
        if total_frames == 0:
            raise PipelineError(self.t("w_no_frames"))

        audio_path = os.path.join(temp_dir, "audio.m4a")
        audio_final = audio_path
        if info["has_audio"]:
            self.status.emit(self.t("w_separating_audio"))
            run_ffmpeg(
                [tools.FFMPEG_EXE, "-y", "-i", self.input_path, "-vn", "-acodec", "copy", audio_path],
                self.t("w_extract_audio_failed"),
            )

            if self.audio_mode != "off":
                audio_final = os.path.join(temp_dir, "audio_boosted.m4a")
                if self.audio_mode == "auto":
                    gain = analyze_audio_gain(audio_path, self.log)
                    if gain > 0.1:
                        self.status.emit(self.t("w_boosting_audio_gain", gain=gain))
                        run_ffmpeg(
                            [tools.FFMPEG_EXE, "-y", "-i", audio_path, "-af", f"volume={gain:.1f}dB", audio_final],
                            self.t("w_boost_audio_failed"),
                        )
                    else:
                        audio_final = audio_path
                else:
                    mult = {"25": 1.25, "50": 1.5, "100": 2.0}.get(self.audio_mode, 1.0)
                    self.status.emit(self.t("w_boosting_audio_mult", mult=mult))
                    run_ffmpeg(
                        [tools.FFMPEG_EXE, "-y", "-i", audio_path, "-af", f"volume={mult}", audio_final],
                        self.t("w_boost_audio_failed"),
                    )

        self.progress.emit(5)
        if self._cancelled:
            return

        model = BENCHMARKS[self.quality_key]["model"]
        engine_scale = engine_scale_for(model, self.scale)
        stall_limit = stall_timeout_for_job(info, self.quality_key, engine_scale)
        scale_note = (
            f"{engine_scale}x→{self.scale}x"
            if needs_post_downscale(model, self.scale)
            else f"{self.scale}x"
        )
        per_frame = format_duration(
            estimate_seconds_per_frame(info, self.quality_key, engine_scale),
            units=self._duration_units(),
        )
        self.log(
            self.t(
                "w_upscaling_video",
                model=model,
                scale_note=scale_note,
                per_frame=per_frame,
                stall=int(stall_limit),
            )
        )
        if not self._run_realesrgan_frames(
            frames_in, frames_out, model, self.scale, stall_limit, total_frames
        ):
            return

        self.progress.emit(95)
        self.status.emit(self.t("w_merging_video"))

        base, _ = os.path.splitext(self.input_path)
        output_path = f"{base}_PixLift_{self.scale}x.mp4"

        vf_parts = []
        if needs_post_downscale(model, self.scale):
            tw, th = target_size(info, self.scale)
            vf_parts.append(f"scale={tw}:{th}:flags=lanczos")
        if self.output_fps:
            vf_parts.append(f"fps={self.output_fps}")

        frame_pattern = os.path.join(frames_out, "frame_%05d.png")

        def build_merge_cmd(with_audio):
            cmd = [
                tools.FFMPEG_EXE, "-y",
                "-framerate", str(info["fps"]),
                "-i", frame_pattern,
            ]
            if with_audio:
                cmd += ["-i", audio_final]
            if vf_parts:
                cmd += ["-vf", ",".join(vf_parts)]
            cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p"]
            if with_audio:
                # fps degisince yeniden encode guvenli; kaynak kanal duzeni
                # (orn. 5.1(side)) native aac encoder'i acamayabildigi icin
                # stereo/48kHz'e normalize ediyoruz.
                cmd += ["-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "48000", "-shortest"]
            cmd += [output_path]
            return cmd

        audio_dropped = False
        result = run_hidden(build_merge_cmd(with_audio=info["has_audio"]))
        if result.returncode != 0:
            if info["has_audio"]:
                # Ses birlestirme basarisiz olabilir (orn. FFmpeg'in native aac
                # encoder'i bazi kanal duzenlerini reddediyor) - tamamlanmis
                # buyutme isini kaybetmemek icin videoyu sessiz olarak dene.
                retry = run_hidden(build_merge_cmd(with_audio=False))
                if retry.returncode != 0:
                    raise PipelineError(format_error(self.t("w_merge_failed"), retry.stderr))
                audio_dropped = True
            else:
                raise PipelineError(format_error(self.t("w_merge_failed"), result.stderr))

        self.progress.emit(100)
        if audio_dropped:
            self.warning.emit(self.t("audio_dropped_warning"))
        self.finished_ok.emit(output_path)

    def _run_gif_pipeline(self, temp_dir):
        info = probe_video(self.input_path)
        frames_in = os.path.join(temp_dir, "frames_in")
        frames_out = os.path.join(temp_dir, "frames_out")
        os.makedirs(frames_in, exist_ok=True)
        os.makedirs(frames_out, exist_ok=True)

        self.status.emit(self.t("w_extracting_frames"))
        self.progress.emit(1)
        run_ffmpeg(
            [
                tools.FFMPEG_EXE, "-y", "-i", self.input_path,
                "-qscale:v", "2",
                os.path.join(frames_in, "frame_%05d.png"),
            ],
            self.t("w_extract_frames_failed"),
        )
        if self._cancelled:
            return

        total_frames = len([f for f in os.listdir(frames_in) if f.endswith(".png")])
        if total_frames == 0:
            raise PipelineError(self.t("w_no_frames"))

        self.progress.emit(5)

        model = BENCHMARKS[self.quality_key]["model"]
        engine_scale = engine_scale_for(model, self.scale)
        stall_limit = stall_timeout_for_job(info, self.quality_key, engine_scale)
        scale_note = (
            f"{engine_scale}x→{self.scale}x"
            if needs_post_downscale(model, self.scale)
            else f"{self.scale}x"
        )
        self.log(self.t("w_upscaling_gif", model=model, scale_note=scale_note, stall=int(stall_limit)))
        if not self._run_realesrgan_frames(
            frames_in, frames_out, model, self.scale, stall_limit, total_frames
        ):
            return

        self.progress.emit(95)
        self.status.emit(self.t("w_merging_gif"))

        base, _ = os.path.splitext(self.input_path)
        output_path = f"{base}_PixLift_{self.scale}x.gif"

        # Duz -pix_fmt yerine palette uretip kullanmak (256 renk sinirlamasinda)
        # buyutulmus kareler icin cok daha az bantlanma/renk bozulmasi verir.
        pre = []
        if needs_post_downscale(model, self.scale):
            tw, th = target_size(info, self.scale)
            pre.append(f"scale={tw}:{th}:flags=lanczos")
        if self.output_fps:
            pre.append(f"fps={self.output_fps}")
        pre_vf = ",".join(pre) + "," if pre else ""
        run_ffmpeg(
            [
                tools.FFMPEG_EXE, "-y",
                "-framerate", str(info["fps"]),
                "-i", os.path.join(frames_out, "frame_%05d.png"),
                "-vf", pre_vf + "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                "-loop", "0",
                output_path,
            ],
            self.t("w_merge_failed"),
        )

        self.progress.emit(100)
        self.finished_ok.emit(output_path)
