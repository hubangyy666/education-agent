"""Prepare the offline precision reward from Kenney's CC0 human voice recording.

Run with Python, numpy and soundfile. No model, speech synthesis or ordinary
encouragement audio is used. The original download and recording are hash pinned.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import copy
import io
import json
from pathlib import Path
import urllib.request
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PAGE = "https://kenney.nl/assets/voiceover-pack"
SOURCE_URL = "https://kenney.nl/media/pages/assets/voiceover-pack/3f7f168698-1677589897/kenney_voiceover-pack.zip"
SOURCE_SHA256 = "a5194df2f05f7ec439a8d4c1a7c20ba12ffe700d363a0733ae6fa826846af458"
SOURCE_MEMBER = "Male/congratulations.ogg"
RECORDING_SHA256 = "9e8421f498ec6434a7c3d5101e29960e13301154076b927180a25fb6d6578e26"
ANIMATION_SHA256 = "051f6a3b9bd184ce10e88d9e71584f19b7311b639a00626c73981acfe74a9927"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def prepare_animation() -> None:
    """Derive a single transparent check from the previously downloaded Lottie."""
    base = ROOT / "public" / "animations"
    original = (base / "success-confetti.json").read_bytes()
    if digest(original) != ANIMATION_SHA256:
        raise RuntimeError("Original Lottie does not match the pinned source")
    source = json.loads(original)
    composition = next(asset for asset in source["assets"] if asset["id"] == "lij4kk2xnijmzwuwob")
    kept = {87393, 95549, 48522}  # Root transform, check transform, check path.
    layers = copy.deepcopy([layer for layer in composition["layers"] if layer.get("ind") in kept])
    if len(layers) != 3:
        raise RuntimeError("Expected the original check shape and its two transforms")
    for layer in layers:
        if layer["ind"] == 95549:
            layer["ks"]["p"]["k"] = [55.0, 55.0]
        elif layer["ind"] == 48522:
            fill = next(item for item in layer["shapes"][0]["it"] if item["ty"] == "fl")
            fill["c"]["k"] = [56 / 255, 161 / 255, 105 / 255, 1]
    result = {
        "v": source["v"], "fr": source["fr"], "ip": 19, "op": 110,
        "w": 110, "h": 110, "nm": "Precision checkmark (derived)",
        "assets": [], "layers": layers, "markers": [],
    }
    target = base / "success-checkmark.json"
    target.write_text(json.dumps(result, separators=(",", ":")) + "\n", encoding="utf-8")
    manifest = {
        "file": target.name,
        "sha256": digest(target.read_bytes()),
        "source_file": "success-confetti.json",
        "source_sha256": ANIMATION_SHA256,
        "source_page": "https://lottiefiles.com/free-animation/success-confetti-mX0p5zY7XU",
        "creator": "Ismail Tofey (AUX)",
        "license": "Lottie Simple License (FL 9.13.21)",
        "license_url": "https://lottiefiles.com/page/license",
        "modifications": "Retain only original check path (48522), check transform (95549) and root transform (87393); remove every background, circle and confetti layer; recolor check green (#38a169), recenter/crop to 110x110, play frames 19-110. Transparent JSON; component supplies only a white circle with no border or shadow.",
    }
    (base / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    import numpy as np
    import soundfile as sf

    cache = ROOT / ".runtime" / "reward-source"
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / "kenney_voiceover-pack.zip"
    if not archive.exists():
        with urllib.request.urlopen(SOURCE_URL, timeout=60) as response:
            downloaded = response.read()
        if digest(downloaded) != SOURCE_SHA256:
            raise RuntimeError("Downloaded voice pack does not match the pinned source")
        archive.write_bytes(downloaded)
    if digest(archive.read_bytes()) != SOURCE_SHA256:
        raise RuntimeError("Cached voice pack does not match the pinned source")

    output = ROOT / "public" / "audio" / "precision"
    output.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive) as source:
        recording = source.read(SOURCE_MEMBER)
        if digest(recording) != RECORDING_SHA256:
            raise RuntimeError("Voice recording does not match the pinned source")
        samples, rate = sf.read(io.BytesIO(recording), dtype="float64")
        if samples.ndim != 1:
            raise RuntimeError("Expected the original mono recording")
        for original, target in [("License.txt", "KENNEY-LICENSE.txt"), ("Credits.txt", "CREDITS.txt")]:
            text = source.read(original).decode("utf-8").replace("\r\r\n", "\n").replace("\r\n", "\n")
            (output / target).write_text(text.strip() + "\n", encoding="utf-8")

    # Retain the complete spoken phrase, timing, original sample rate and pitch.
    # Only normalize peak volume and transcode OGG to browser-compatible PCM WAV.
    peak = float(np.max(np.abs(samples)))
    if peak <= .01:
        raise RuntimeError("Source recording is silent")
    samples *= (10 ** (-3 / 20)) / peak
    reward = output / "congratulations.wav"
    sf.write(reward, samples, rate, subtype="PCM_16")
    decoded, decoded_rate = sf.read(reward)
    duration = len(decoded) / decoded_rate
    rms = float(np.sqrt(np.mean(decoded ** 2)))
    if decoded_rate != rate or not .5 < duration < 2 or rms < .01:
        raise RuntimeError("Decoded precision reward quality check failed")
    manifest = {
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "trigger": "annotation IoU > 0.90 after deterministic grading",
        "file": reward.name,
        "spoken_text": "Congratulations!",
        "duration_seconds": round(duration, 6),
        "format": "WAV PCM signed 16-bit mono",
        "sample_rate": rate,
        "sha256": digest(reward.read_bytes()),
        "rms": round(rms, 6),
        "peak": round(float(np.max(np.abs(decoded))), 6),
        "speech": {
            "kind": "downloaded human voice recording",
            "creator": "Kenney",
            "voice_actor": "Jeffrey M. Smith",
            "voice": "male",
            "page": SOURCE_PAGE,
            "source_url": SOURCE_URL,
            "source_sha256": SOURCE_SHA256,
            "archive_member": SOURCE_MEMBER,
            "recording_sha256": RECORDING_SHA256,
            "license": "CC0-1.0",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        },
        "processing": "Original complete mono recording; original sample rate and pitch; peak normalized to -3dB; OGG decoded to PCM 16-bit WAV; no synthesis or mixing",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    prepare_animation()
    print(f"Prepared {reward}: {duration:.3f}s, {rate}Hz", flush=True)


if __name__ == "__main__":
    main()
