# translator\n\n**Phone se test karna hai? → [Open in Colab](https://colab.research.google.com/github/warisrauf34/SHAZI/blob/claude/folder-question-x2uwgy/translator.ipynb)** (kuch install nahi karna, sirf Groq key + YouTube URL).\n

End-to-end pipeline to translate a YouTube video's audio into another language:

1. Download the video (`yt-dlp`)
2. Transcribe with **Groq Whisper** (`whisper-large-v3`, fast)
3. Translate segments with **Groq LLM** (`llama-3.3-70b-versatile`)
4. Generate voiceover with **Edge-TTS** (free, high quality)
5. Mute original audio, mux new voiceover into the video, auto-adjusting
   timing so voice and picture stay in sync (per-segment: stretch the
   voice for small mismatches, stretch/trim the video for large ones)

## Install

```bash
# System deps
sudo apt-get install -y ffmpeg
pip install -U yt-dlp

# Python deps
pip install -r requirements.txt
```

## Configure

Copy `.env.example` → `.env` and set:

```
GROQ_API_KEY=gsk_...
```

## Run

```bash
python -m translator "https://www.youtube.com/watch?v=..." \
  --lang ur \
  --voice ur-PK-AsadNeural \
  --workdir ./out
```

Result: `./out/translated.mp4`

### Common voices (Edge-TTS)

| Lang | Voice |
|------|-------|
| Urdu | `ur-PK-AsadNeural` (M), `ur-PK-UzmaNeural` (F) |
| Hindi | `hi-IN-MadhurNeural` (M), `hi-IN-SwaraNeural` (F) |
| English (US) | `en-US-GuyNeural` (M), `en-US-JennyNeural` (F) |
| Spanish | `es-ES-AlvaroNeural` (M), `es-ES-ElviraNeural` (F) |
| Arabic | `ar-SA-HamedNeural` (M), `ar-SA-ZariyahNeural` (F) |

List all: `edge-tts --list-voices`

## Known limitations

- Groq's transcription endpoint has a **25 MB file limit** — very long
  videos need chunking (not implemented yet; will fail loudly).
- If the translated voiceover is **much** longer/shorter than the original
  segment, the pipeline stretches the *video* (setpts) as a fallback. That
  keeps the voice natural but can look slightly sped-up/slowed-down. Set
  `--sync natural` to insert silence padding instead (video untouched).
- Edge-TTS is free but rate-limited; for hours of content ElevenLabs will
  be more robust.
