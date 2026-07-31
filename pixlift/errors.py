"""Pipeline hata turleri ve ffmpeg calistirma yardimcisi."""

from .tools import run_hidden


class PipelineError(Exception):
    """Kullaniciya gosterilecek kisa ozet + (varsa) ffmpeg log kuyrugu."""


def run_ffmpeg(args, summary, log=None):
    """ffmpeg calistir; basarisizsa PipelineError(ozet + log kuyrugu) firlat.

    Tam stderr `log` varsa oraya yazilir (debug icin); kullaniciya sadece
    son ~800 karakterlik kuyruk gosterilir.
    """
    result = run_hidden(args)
    if result.returncode != 0:
        if log:
            log(f"[ffmpeg] {' '.join(args)}\n{result.stderr}")
        tail = result.stderr[-800:].strip()
        detail = f":\n{tail}" if tail else ""
        raise PipelineError(f"{summary}{detail}")
    return result
