"""Transcribe audio with Groq's Whisper endpoint. Fast + segment timestamps."""
import os
from pathlib import Path

import requests

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MAX_MB = 25  # Groq hard limit for the audio endpoint.


def transcribe_with_groq(audio: Path, model: str = "whisper-large-v3") -> list[dict]:
    """Returns [{start, end, text, id}, ...] using verbose_json.

    Raises RuntimeError if the file exceeds Groq's 25 MB limit (chunking
    not implemented yet — flagged as a known limitation in the README).
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")

    size_mb = audio.stat().st_size / (1024 * 1024)
    if size_mb > MAX_MB:
        raise RuntimeError(
            f"Audio file {audio.name} is {size_mb:.1f} MB, exceeding Groq's "
            f"{MAX_MB} MB limit. Chunk the audio (e.g., ffmpeg -f segment) and "
            f"transcribe pieces, then offset timestamps."
        )

    with audio.open("rb") as f:
        r = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (audio.name, f, "audio/wav")},
            data={
                "model": model,
                "response_format": "verbose_json",
                "timestamp_granularities[]": "segment",
            },
            timeout=600,
        )
    r.raise_for_status()
    data = r.json()

    segments = []
    for s in data.get("segments", []):
        text = (s.get("text") or "").strip()
        if not text:
            continue
        segments.append({
            "id": len(segments),
            "start": float(s["start"]),
            "end": float(s["end"]),
            "text": text,
        })
    return segments
