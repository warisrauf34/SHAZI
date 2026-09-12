"""Translate segments using Groq's chat completions API."""
import os
import re

import requests

GROQ_CHAT = "https://api.groq.com/openai/v1/chat/completions"

LANG_NAMES = {
    "ur": "Urdu", "hi": "Hindi", "en": "English", "es": "Spanish",
    "fr": "French", "de": "German", "ar": "Arabic", "zh": "Chinese",
    "ja": "Japanese", "ko": "Korean", "pt": "Portuguese",
    "ru": "Russian", "tr": "Turkish", "it": "Italian",
}

BATCH = 40  # translate this many segments per request to keep prompts small


def translate_segments(
    segments: list[dict],
    lang: str,
    model: str = "llama-3.3-70b-versatile",
) -> list[dict]:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")
    lang_name = LANG_NAMES.get(lang, lang)

    out = list(segments)  # copy so we can overwrite text field
    for start in range(0, len(segments), BATCH):
        chunk = segments[start:start + BATCH]
        translations = _translate_chunk(chunk, lang_name, api_key, model)
        for local_i, translated_text in translations.items():
            out[start + local_i] = {**chunk[local_i], "text": translated_text}
    return out


def _translate_chunk(chunk, lang_name, api_key, model) -> dict[int, str]:
    numbered = "\n".join(f"[{i}] {s['text']}" for i, s in enumerate(chunk))
    system = (
        f"You are a professional subtitle translator. Translate each numbered "
        f"line into {lang_name}. Keep the [index] tag at the start. Output "
        f"exactly one translated line per input line, in order. Preserve tone "
        f"and speaker intent. Do not merge, split, or add commentary."
    )
    r = requests.post(
        GROQ_CHAT,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": numbered},
            ],
        },
        timeout=300,
    )
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]

    result: dict[int, str] = {}
    for line in content.splitlines():
        m = re.match(r"^\s*\[(\d+)\]\s*(.*)$", line)
        if not m:
            continue
        idx = int(m.group(1))
        text = m.group(2).strip()
        if text:
            result[idx] = text
    return result
