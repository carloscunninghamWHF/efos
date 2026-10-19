"""Vídeo del partido: sincronización evento → vídeo, recorte de clips y MP4 clip + animación."""
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "visualization"))
import match_video as MV  # noqa: E402


def test_clock_parsing_and_format():
    assert MV.parse_clock("12:30") == 750 and MV.parse_clock("1:02:03") == 3723 and MV.parse_clock("90") == 90
    assert MV.parse_clock("") is None and MV.parse_clock("abc") is None
    assert MV.fmt_clock(750) == "12:30" and MV.fmt_clock(3723) == "1:02:03"


def test_sync_uses_period_clock():
    cfg = {"fuente": "x.mp4", "inicio_1": 120.0, "inicio_2": 3600.0}
    e1 = pd.Series({"period": 1, "timestamp": "00:10:05.500", "minute": 10, "second": 5})
    e2 = pd.Series({"period": 2, "timestamp": "00:01:00.000", "minute": 46, "second": 0})
    assert MV.video_time(e1, cfg) == pytest.approx(120 + 605.5)
    assert MV.video_time(e2, cfg) == pytest.approx(3600 + 60)
    # sin `timestamp`: minuto y segundo menos el inicio de la parte
    e3 = pd.Series({"period": 2, "timestamp": None, "minute": 46, "second": 0})
    assert MV.video_time(e3, cfg) == pytest.approx(3660)
    a, b = MV.clip_window(e1, cfg, 9.0)
    assert a == pytest.approx(725.5 - MV.PRE_ROLL) and b - a == pytest.approx(MV.PRE_ROLL + 9 + MV.POST_ROLL)
    assert MV.video_time(pd.Series({"period": 3, "timestamp": "00:00:10"}), cfg) is None


def test_config_roundtrip(tmp_path):
    p = tmp_path / "v" / "videos.json"
    MV.save_match(4001, "partido.mp4", 90, 3500, path=p)
    assert MV.load_config(p)["4001"] == {"fuente": "partido.mp4", "inicio_1": 90.0, "inicio_2": 3500.0}
    assert MV.resolve_source("https://x.org/a.mp4") == "https://x.org/a.mp4"
    assert MV.resolve_source("a.mp4", folder=tmp_path) == str(tmp_path / "a.mp4")


@pytest.mark.skipif(MV.ffmpeg_exe() is None, reason="sin ffmpeg")
def test_clip_and_sequence(tmp_path):
    src = tmp_path / "m.mp4"
    subprocess.run([MV.ffmpeg_exe(), "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25:duration=12",
                    "-f", "lavfi", "-i", "sine=duration=12", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest",
                    str(src)], check=True)
    clip = MV.moment_clip(str(src), 1, "abc", (3.0, 7.0), cache=tmp_path / "clips")
    out = next((tmp_path / "clips").iterdir())
    assert clip[4:8] == b"ftyp" and MV.duration(str(out)) == pytest.approx(4, abs=0.3) and MV.has_audio(str(out))
    anim = tmp_path / "a.mp4"
    subprocess.run([MV.ffmpeg_exe(), "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=white:size=600x500:rate=12:duration=3",
                    "-pix_fmt", "yuv420p", str(anim)], check=True)
    seq = MV.sequence_mp4(clip, anim.read_bytes(), size=(640, 360))
    (tmp_path / "s.mp4").write_bytes(seq)
    assert MV.duration(str(tmp_path / "s.mp4")) == pytest.approx(7, abs=0.4)
    assert MV.frame_at(str(src), 5)[:2] == b"\xff\xd8"
