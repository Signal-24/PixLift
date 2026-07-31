"""Pipeline hata turleri ve ffmpeg calistirma yardimcisi."""

from .tools import run_hidden


class PipelineError(Exception):
    """Kullaniciya gosterilecek kisa ozet + (varsa) ffmpeg log kuyrugu."""


def format_error(summary, stderr):
    """Kisa ozet + son ~800 karakterlik stderr kuyrugunu tek mesajda birlestir."""
    tail = (stderr or "")[-800:].strip()
    return f"{summary}:\n{tail}" if tail else summary


def run_ffmpeg(args, summary):
    """ffmpeg calistir; basarisizsa PipelineError(ozet + stderr kuyrugu) firlat."""
    result = run_hidden(args)
    if result.returncode != 0:
        raise PipelineError(format_error(summary, result.stderr))
    return result
