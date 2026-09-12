"""Generate per-segment voiceover clips using Edge-TTS."""
import asyncio
from pathlib import Path

import edge_tts


def synthesize_segments(segments: list[dict], voice: str, outdir: Path) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, seg in enumerate(segments):
        out = outdir / f"clip_{i:04d}.mp3"
        text = seg["text"].strip()
        if not text:
            # Empty text: create a tiny silence file so indices stay aligned.
            _write_silence(out, duration=0.3)
        else:
            asyncio.run(_synth(text, voice, out))
        paths.append(out)
    return paths


async def _synth(text: str, voice: str, out: Path) -> None:
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(out))


def _write_silence(out: Path, duration: float) -> None:
    import subprocess
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"anullsrc=r=24000:cl=mono", "-t", f"{duration}",
         "-q:a", "9", str(out)],
        check=True, capture_output=True,
    )
