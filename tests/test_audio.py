from atado.audio import ffmpeg_normalize_args, is_supported, SUPPORTED_EXTS


def test_normalize_args_mono_16k_wav():
    args = ffmpeg_normalize_args("in.mp3", "out.wav")
    assert args[0] == "ffmpeg"
    assert "-ac" in args and args[args.index("-ac") + 1] == "1"
    assert "-ar" in args and args[args.index("-ar") + 1] == "16000"
    assert args[-1] == "out.wav"
    assert "in.mp3" in args


def test_video_inputs_supported():
    assert is_supported("reuniao.mp4")
    assert is_supported("clip.mkv")
    assert is_supported("nota.ogg")
    assert is_supported("audio.OPUS")  # case-insensitive


def test_unsupported_extension():
    assert not is_supported("documento.pdf")


def test_supported_covers_whatsapp_formats():
    for ext in ("mp3", "m4a", "ogg", "opus", "wav", "flac"):
        assert ext in SUPPORTED_EXTS
