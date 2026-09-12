"""End-to-end video translation pipeline entry point."""
import argparse
import json
import subprocess
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from .downloader import download_video
from .transcriber import transcribe_with_groq
from .translator_service import translate_segments
from .video_mixer import mix_video_with_voiceover
from .voiceover import synthesize_segments


def run(url: str, target_lang: str, voice: str, workdir: Path) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)

    print(f"[1/5] Downloading video → {workdir}/source.mp4")
    video_path = download_video(url, workdir / "source.mp4")

    print("[2/5] Extracting audio and transcribing with Groq Whisper")
    audio_path = workdir / "source.wav"
    _extract_audio(video_path, audio_path)
    segments = transcribe_with_groq(audio_path)
    (workdir / "transcript.json").write_text(
        json.dumps(segments, ensure_ascii=False, indent=2)
    )
    print(f"      → {len(segments)} segments transcribed")

    print(f"[3/5] Translating to '{target_lang}' with Groq LLM")
    translated = translate_segments(segments, target_lang)
    (workdir / "translated.json").write_text(
        json.dumps(translated, ensure_ascii=False, indent=2)
    )

    print(f"[4/5] Synthesizing voiceover with Edge-TTS ({voice})")
    clips = synthesize_segments(translated, voice, workdir / "clips")

    print("[5/5] Muxing new voiceover into video (auto sync)")
    out = workdir / "translated.mp4"
    mix_video_with_voiceover(video_path, translated, clips, out)

    print(f"\n✓ Done: {out}")
    return out


def _extract_audio(video: Path, out: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video),
         "-vn", "-ac", "1", "-ar", "16000",
         str(out)],
        check=True, capture_output=True,
    )


def main():
    ap = argparse.ArgumentParser(
        prog="translator",
        description="Translate a YouTube video's audio into another language.",
    )
    ap.add_argument("url", help="YouTube video URL")
    ap.add_argument("--lang", default="ur",
                    help="Target language code (e.g. ur, hi, es, en). Default: ur")
    ap.add_argument("--voice", default="ur-PK-AsadNeural",
                    help="Edge-TTS voice name. Default: ur-PK-AsadNeural")
    ap.add_argument("--workdir", default="./out",
                    help="Working / output directory. Default: ./out")
    args = ap.parse_args()

    run(args.url, args.lang, args.voice, Path(args.workdir))


if __name__ == "__main__":
    main()
