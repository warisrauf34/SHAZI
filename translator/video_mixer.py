"""Assemble the final video from the original picture + translated voiceover.

For each transcribed segment we get a slice of the original video and a TTS
clip. We compare their durations and pick a strategy:

  ratio = tts_duration / video_slot_duration

  - 0.9 <= ratio <= 1.1  : leave both as-is (near-perfect fit)
  - 0.5 <= ratio <= 2.0  : atempo the TTS to fit the video slot
  - otherwise            : stretch/trim the *video* (setpts) so the voice
                           stays natural — this is the "big mismatch"
                           fallback the user asked for

We also carry the between-segment gaps forward as silent slices from the
original video so B-roll and pauses survive.
"""
import subprocess
from pathlib import Path


def probe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(r.stdout.strip())


def atempo_chain(speed: float) -> str:
    """ffmpeg's atempo accepts 0.5..2.0 per instance; chain for larger ratios."""
    speed = max(0.25, min(4.0, speed))
    parts = []
    remaining = speed
    while remaining < 0.5:
        parts.append("atempo=0.5")
        remaining /= 0.5
    while remaining > 2.0:
        parts.append("atempo=2.0")
        remaining /= 2.0
    parts.append(f"atempo={remaining:.4f}")
    return ",".join(parts)


def mix_video_with_voiceover(
    video: Path,
    segments: list[dict],
    clips: list[Path],
    out: Path,
) -> None:
    tmp = out.parent / "_pieces"
    tmp.mkdir(exist_ok=True)

    total_dur = probe_duration(video)
    pieces: list[Path] = []
    cursor = 0.0

    for i, (seg, clip) in enumerate(zip(segments, clips)):
        # Any gap before this segment is included as-is (silent, keeps picture).
        if seg["start"] > cursor + 0.05:
            gap = tmp / f"gap_{i:04d}.mp4"
            _cut_silent(video, cursor, seg["start"] - cursor, gap)
            pieces.append(gap)

        piece = tmp / f"piece_{i:04d}.mp4"
        v_dur = max(0.1, seg["end"] - seg["start"])
        a_dur = probe_duration(clip)
        _build_piece(video, seg["start"], v_dur, clip, a_dur, piece)
        pieces.append(piece)
        cursor = seg["end"]

    # Tail after the last segment.
    if total_dur > cursor + 0.05:
        tail = tmp / "tail.mp4"
        _cut_silent(video, cursor, total_dur - cursor, tail)
        pieces.append(tail)

    concat = tmp / "concat.txt"
    concat.write_text("".join(f"file '{p.resolve()}'\n" for p in pieces))
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart",
         str(out)],
        check=True,
    )


def _cut_silent(video: Path, start: float, dur: float, out: Path) -> None:
    """Cut a slice of the video and replace its audio with silence."""
    subprocess.run(
        ["ffmpeg", "-y",
         "-ss", f"{start}", "-t", f"{dur}", "-i", str(video),
         "-f", "lavfi", "-t", f"{dur}", "-i", "anullsrc=r=48000:cl=stereo",
         "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-c:a", "aac", "-b:a", "192k",
         "-shortest",
         str(out)],
        check=True, capture_output=True,
    )


def _build_piece(
    video: Path, start: float, v_dur: float,
    clip: Path, a_dur: float, out: Path,
) -> None:
    ratio = a_dur / v_dur

    if 0.9 <= ratio <= 1.1:
        # Near-perfect fit: use both as-is, trim to the shorter of the two.
        target = min(v_dur, a_dur)
        subprocess.run(
            ["ffmpeg", "-y",
             "-ss", f"{start}", "-t", f"{target}", "-i", str(video),
             "-i", str(clip),
             "-map", "0:v", "-map", "1:a",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-c:a", "aac", "-b:a", "192k", "-shortest",
             str(out)],
            check=True, capture_output=True,
        )
        return

    if 0.5 <= ratio <= 2.0:
        # Speed up / slow down the TTS to fit the original video slot.
        # atempo speed = a_dur / v_dur  (so new_dur = a_dur / speed = v_dur)
        atempo = atempo_chain(a_dur / v_dur)
        subprocess.run(
            ["ffmpeg", "-y",
             "-ss", f"{start}", "-t", f"{v_dur}", "-i", str(video),
             "-i", str(clip),
             "-filter_complex", f"[1:a]{atempo}[aout]",
             "-map", "0:v", "-map", "[aout]",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-c:a", "aac", "-b:a", "192k", "-shortest",
             str(out)],
            check=True, capture_output=True,
        )
        return

    # Large mismatch: keep voice natural, stretch/trim the video instead.
    # If TTS is longer  -> slow video down (setpts * ratio)
    # If TTS is shorter -> speed video up  (setpts * ratio)
    setpts_factor = ratio  # new_video_dur = v_dur * ratio = a_dur
    subprocess.run(
        ["ffmpeg", "-y",
         "-ss", f"{start}", "-t", f"{v_dur}", "-i", str(video),
         "-i", str(clip),
         "-filter_complex",
         f"[0:v]setpts={setpts_factor:.4f}*PTS[vout]",
         "-map", "[vout]", "-map", "1:a",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-c:a", "aac", "-b:a", "192k", "-shortest",
         str(out)],
        check=True, capture_output=True,
    )
