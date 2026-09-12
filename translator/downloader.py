"""Download a YouTube video as mp4 using yt-dlp."""
import subprocess
from pathlib import Path


def download_video(url: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "yt-dlp",
            "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
            "--merge-output-format", "mp4",
            "-o", str(out),
            url,
        ],
        check=True,
    )
    if not out.exists():
        raise RuntimeError(f"yt-dlp did not produce {out}")
    return out
