from pixlift.media import (
    engine_scale_for,
    estimate_seconds,
    estimate_seconds_per_frame,
    even_dim,
    format_duration,
    image_output_format,
    is_gif_file,
    is_image_file,
    low_bitrate_risk,
    needs_post_downscale,
    stall_timeout_for_job,
    target_size,
)


def test_is_image_file():
    assert is_image_file("photo.JPG")
    assert is_image_file("photo.webp")
    assert not is_image_file("clip.mp4")
    assert not is_image_file("anim.gif")


def test_is_gif_file():
    assert is_gif_file("anim.GIF")
    assert not is_gif_file("clip.mp4")


def test_image_output_format():
    assert image_output_format(".jpeg") == "jpg"
    assert image_output_format(".JPG") == "jpg"
    assert image_output_format(".png") == "png"
    assert image_output_format(".webp") == "webp"
    assert image_output_format(".bmp") == "png"


def test_engine_scale_for_native_model_ignores_requested_scale():
    assert engine_scale_for("realesrgan-x4plus", 2) == 4
    assert engine_scale_for("realesrgan-x4plus", 3) == 4


def test_engine_scale_for_non_native_model_uses_requested_scale():
    assert engine_scale_for("realesr-animevideov3", 2) == 2
    assert engine_scale_for("realesr-animevideov3", 3) == 3


def test_needs_post_downscale():
    assert needs_post_downscale("realesrgan-x4plus", 2) is True
    assert needs_post_downscale("realesrgan-x4plus", 4) is False
    assert needs_post_downscale("realesr-animevideov3", 2) is False


def test_even_dim():
    assert even_dim(100) == 100
    assert even_dim(101) == 100
    assert even_dim(1) == 0


def test_target_size_rounds_down_to_even():
    info = {"width": 101, "height": 51}
    assert target_size(info, 2) == (202, 102)
    assert target_size(info, 3) == (302, 152)


def test_estimate_seconds_scales_with_pixels_and_frames():
    bench_px_info = {"width": 950, "height": 718, "frame_count": 10}
    seconds = estimate_seconds(bench_px_info, "fast")
    assert seconds == 1.5 * 10


def test_estimate_seconds_per_frame_has_floor():
    tiny_info = {"width": 1, "height": 1}
    assert estimate_seconds_per_frame(tiny_info, "fast", scale=2) == 1.0


def test_stall_timeout_for_job_respects_minimum():
    small_info = {"width": 100, "height": 100}
    assert stall_timeout_for_job(small_info, "fast", scale=2) == 120


def test_format_duration_default_units():
    assert format_duration(45) == "~45 sn"
    assert format_duration(300) == "~5 dk"
    assert format_duration(7200) == "~2.0 saat"


def test_format_duration_custom_units():
    units = {"sec": "sec", "min": "min", "hr": "hr"}
    assert format_duration(45, units=units) == "~45 sec"
    assert format_duration(300, units=units) == "~5 min"
    assert format_duration(7200, units=units) == "~2.0 hr"


def test_low_bitrate_risk():
    low = {"bitrate": 500_000, "width": 1920, "height": 1080, "fps": 30}
    high = {"bitrate": 20_000_000, "width": 1920, "height": 1080, "fps": 30}
    unknown = {"bitrate": 0, "width": 1920, "height": 1080, "fps": 30}
    assert low_bitrate_risk(low) is True
    assert low_bitrate_risk(high) is False
    assert low_bitrate_risk(unknown) is False
