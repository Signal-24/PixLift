"""Buyutme pipeline'i: kare cikarma/birlestirme, ses isleme, Real-ESRGAN calistirma."""

import os
import shutil
import subprocess
import tempfile
import time

from PySide6.QtCore import QThread, Signal

from . import tools
from .errors import EngineOutputError, PipelineError, format_error, run_ffmpeg
from .media import (
    BENCHMARKS,
    STALL_TIMEOUT_MIN_SECONDS,
    STALL_TIMEOUT_SECONDS,
    TILE_FALLBACKS,
    analyze_audio_gain,
    engine_scale_for,
    engine_stderr_problem,
    estimate_seconds_per_frame,
    format_duration,
    image_output_format,
    image_sample,
    is_gif_file,
    is_image_file,
    looks_corrupt,
    needs_post_downscale,
    output_problem,
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

    @staticmethod
    def _kill(proc):
        proc.kill()
        try:
            proc.wait(timeout=10)  # dosya tutamaklari birakilsin (yeniden deneme / temizlik icin)
        except subprocess.TimeoutExpired:
            pass

    @staticmethod
    def _read_tail(path, limit=800):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()[-limit:]
        except OSError:
            return ""

    @staticmethod
    def _sorted_frames(folder):
        return sorted(f for f in os.listdir(folder) if f.endswith(".png"))

    def _early_frame_check(self, frames_in, frames_out):
        """Ilk biten karelerden birini girisle karsilastir.

        True: dogrulandi, False: henuz okunamadi (dosya yarim olabilir), bozuksa
        EngineOutputError firlatir. Boylece saatler surecek bir isi bastan durdururuz.
        """
        names = self._sorted_frames(frames_out)
        if len(names) < 2:
            return False
        name = names[0]  # en dusuk numara: sonrakiler de bittigine gore tam yazilmistir
        out_sample = image_sample(os.path.join(frames_out, name))
        if out_sample is None:
            return False
        if looks_corrupt(image_sample(os.path.join(frames_in, name)), out_sample):
            raise EngineOutputError("blank_output")
        return True

    def _wait_realesrgan(self, proc, frames_in, frames_out, total_frames, stall_limit, stderr_path):
        """Real-ESRGAN bitene kadar izle; kare ilerlemesi yoksa stall_limit sonra kes.

        stderr dosyaya yazilir (PIPE + okumamak Windows'ta sureci kilitleyebilir).
        """
        last_done = 0
        last_progress_time = time.time()
        early_checked = False
        while proc.poll() is None:
            if self._cancelled:
                self._kill(proc)
                return False
            done = len(self._sorted_frames(frames_out))
            if not early_checked and done >= 2:
                try:
                    early_checked = self._early_frame_check(frames_in, frames_out)
                except EngineOutputError:
                    self._kill(proc)
                    raise
            if done != last_done:
                last_done = done
                last_progress_time = time.time()
            elif time.time() - last_progress_time > stall_limit:
                self._kill(proc)
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

    def _run_realesrgan_frames(self, frames_in, frames_out, model, scale, stall_limit, total_frames, tile=0):
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
                    "-t", str(tile),
                    "-f", "png",
                ],
                cwd=os.path.dirname(tools.REALESRGAN_EXE),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=stderr_file,
                creationflags=tools.NO_CREATE_WINDOW,
            )
            alive = self._wait_realesrgan(proc, frames_in, frames_out, total_frames, stall_limit, stderr_path)

        if not alive:
            return False

        stderr_tail = self._read_tail(stderr_path)
        if proc.returncode != 0:
            raise EngineOutputError("exit_code", stderr_tail)

        # Motor 0 ile cikip kare yazmamis / siyah yazmis olabilir: cikis koduna guvenme.
        problem = engine_stderr_problem(stderr_tail)
        if problem == "decode_failed":
            raise EngineOutputError(problem, stderr_tail)
        names = self._sorted_frames(frames_out)
        if len(names) < total_frames:
            raise EngineOutputError("missing_frames", f"{len(names)}/{total_frames}\n{stderr_tail}")
        # Son kare (en son yazilan) girisle uyumlu mu?
        last = names[-1]
        if looks_corrupt(
            image_sample(os.path.join(frames_in, last)),
            image_sample(os.path.join(frames_out, last)),
        ):
            raise EngineOutputError("blank_output", stderr_tail)
        if problem == "gpu_error":
            raise EngineOutputError(problem, stderr_tail)
        return True

    def _upscale_frames_with_fallback(self, frames_in, frames_out, model, scale, stall_limit, total_frames):
        """Kareleri buyut; cikti bozuksa daha kucuk parca (tile) boyutuyla otomatik yeniden dene.

        Iptal edilirse False doner. Tum denemeler basarisizsa PipelineError firlatir.
        """
        last_error = None
        for index, tile in enumerate(TILE_FALLBACKS):
            for name in os.listdir(frames_out):  # onceki denemeden kalanlari temizle
                try:
                    os.remove(os.path.join(frames_out, name))
                except OSError:
                    pass
            try:
                return self._run_realesrgan_frames(
                    frames_in, frames_out, model, scale, stall_limit, total_frames, tile=tile
                )
            except EngineOutputError as e:
                last_error = e
                if e.reason == "decode_failed" or index == len(TILE_FALLBACKS) - 1:
                    break
                self.log(
                    self.t(
                        "w_retry_tile",
                        reason=self.t("reason_" + e.reason),
                        tile=TILE_FALLBACKS[index + 1],
                    )
                )
        raise PipelineError(
            format_error(
                self.t("w_output_bad", reason=self.t("reason_" + last_error.reason)),
                last_error.detail,
            )
        )

    def run(self):
        temp_dir = tempfile.mkdtemp(prefix="pixlift_")
        try:
            if is_image_file(self.input_path):
                self._run_image_pipeline(temp_dir)
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

    def _engine_photo_once(
        self, work_path, model, engine_scale, engine_format, tile, estimated_total, stall_limit, stderr_path
    ):
        """Motoru bir kez calistir. Iptal edilirse None, aksi halde (cikis_kodu, stderr) doner."""
        start = time.time()
        with open(stderr_path, "w", encoding="utf-8", errors="replace") as stderr_file:
            proc = subprocess.Popen(
                [
                    tools.REALESRGAN_EXE,
                    "-i", self.input_path,
                    "-o", work_path,
                    "-n", model,
                    "-s", str(engine_scale),
                    "-t", str(tile),
                    "-f", engine_format,
                ],
                cwd=os.path.dirname(tools.REALESRGAN_EXE),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=stderr_file,
                creationflags=tools.NO_CREATE_WINDOW,
            )
            while proc.poll() is None:
                if self._cancelled:
                    self._kill(proc)
                    return None
                elapsed = time.time() - start
                if elapsed > stall_limit:
                    self._kill(proc)
                    raise PipelineError(self.t("w_stall_photo"))
                pct = 5 + int(90 * min(elapsed / estimated_total, 1.0))
                self.progress.emit(min(pct, 95))
                time.sleep(0.2)
        return proc.returncode, self._read_tail(stderr_path, limit=4000)

    def _run_image_pipeline(self, temp_dir):
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
        # Hicbir ara/bozuk sonuc nihai klasore yazilmaz: once gecici klasore yazilir,
        # dogrulandiktan sonra tasinir.
        engine_format = "png" if post_downscale else out_ext
        work_path = os.path.join(temp_dir, f"engine_out.{engine_format}")
        result_path = os.path.join(temp_dir, f"result.{out_ext}") if post_downscale else work_path
        stderr_path = os.path.join(temp_dir, "realesrgan_stderr.log")

        scale_note = f"{engine_scale}x→{self.scale}x" if post_downscale else f"{self.scale}x"
        self.status.emit(self.t("w_upscaling_photo", model=model, scale_note=scale_note))
        self.progress.emit(5)

        stall_limit = max(estimated_total * 4, STALL_TIMEOUT_SECONDS, STALL_TIMEOUT_MIN_SECONDS)
        input_sample = image_sample(self.input_path)
        reason, detail = None, ""
        # Motor siyah/bos cikti yazip 0 ile cikabiliyor (GPU bellegi/surucu); cikis koduna
        # guvenmeyip ciktiyi dogrular, bozuksa daha kucuk parca boyutuyla yeniden deneriz.
        for index, tile in enumerate(TILE_FALLBACKS):
            if os.path.exists(work_path):
                os.remove(work_path)
            outcome = self._engine_photo_once(
                work_path, model, engine_scale, engine_format, tile,
                estimated_total, stall_limit, stderr_path,
            )
            if outcome is None:  # iptal
                return
            returncode, stderr_text = outcome
            reason = output_problem(self.input_path, work_path, returncode, stderr_text, input_sample)
            detail = stderr_text[-800:]
            if reason is None or reason == "decode_failed" or index == len(TILE_FALLBACKS) - 1:
                break
            self.status.emit(
                self.t("w_retry_tile", reason=self.t("reason_" + reason), tile=TILE_FALLBACKS[index + 1])
            )
        if reason is not None:
            raise PipelineError(
                format_error(self.t("w_output_bad", reason=self.t("reason_" + reason)), detail)
            )

        if post_downscale:
            if self._cancelled:
                return
            self.status.emit(self.t("w_downscaling_photo", scale=self.scale))
            tw, th = target_size(info, self.scale)
            run_ffmpeg(
                [
                    tools.FFMPEG_EXE, "-y", "-i", work_path,
                    "-vf", f"scale={tw}:{th}:flags=lanczos",
                    result_path,
                ],
                self.t("w_resize_failed"),
            )

        if self._cancelled:
            return
        shutil.move(result_path, output_path)
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

        # Matroska (.mka) hemen hemen her ses kodekini "copy" ile kabul eder;
        # m4a/mp4 konteyneri ise yalnizca aac/alac ile calisir ve kaynak mp3/opus/vb.
        # oldugunda "codec not currently supported in container" ile patlar.
        audio_path = os.path.join(temp_dir, "audio.mka")
        audio_final = audio_path
        if info["has_audio"]:
            self.status.emit(self.t("w_separating_audio"))
            run_ffmpeg(
                [tools.FFMPEG_EXE, "-y", "-i", self.input_path, "-vn", "-acodec", "copy", audio_path],
                self.t("w_extract_audio_failed"),
            )

            if self.audio_mode != "off":
                audio_final = os.path.join(temp_dir, "audio_boosted.mka")
                # flac: kayipsiz ve aac'nin aksine sıra disi kanal duzenlerinde
                # takilmiyor; nihai aac'ye gecis yalnizca birlestirme adiminda olur.
                if self.audio_mode == "auto":
                    gain = analyze_audio_gain(audio_path, self.log)
                    if gain > 0.1:
                        self.status.emit(self.t("w_boosting_audio_gain", gain=gain))
                        run_ffmpeg(
                            [
                                tools.FFMPEG_EXE, "-y", "-i", audio_path,
                                "-af", f"volume={gain:.1f}dB", "-c:a", "flac", audio_final,
                            ],
                            self.t("w_boost_audio_failed"),
                        )
                    else:
                        audio_final = audio_path
                else:
                    mult = {"25": 1.25, "50": 1.5, "100": 2.0}.get(self.audio_mode, 1.0)
                    self.status.emit(self.t("w_boosting_audio_mult", mult=mult))
                    run_ffmpeg(
                        [
                            tools.FFMPEG_EXE, "-y", "-i", audio_path,
                            "-af", f"volume={mult}", "-c:a", "flac", audio_final,
                        ],
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
        if not self._upscale_frames_with_fallback(
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
        if not self._upscale_frames_with_fallback(
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
