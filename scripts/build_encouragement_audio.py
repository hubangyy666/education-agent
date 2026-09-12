"""Render the bundled Mandarin encouragement pack with a pinned, open-weight model.

Run only when changing audio assets; the application never loads the TTS model.
Install the optional build dependencies in an isolated environment (see docs/voice-feedback.md).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REPO = "hexgrad/Kokoro-82M-v1.1-zh"
REVISION = "01e7505bd6a7a2ac4975463114c3a7650a9f7218"
MODEL_FILE = "kokoro-v1_1-zh.pth"
MODEL_SHA256 = "b1d8410fa44dfb5c15471fd6c4225ea6b4e9ac7fa03c98e8bea47a9928476e2b"
PHRASES = [
    "答对啦，做得很好！",
    "很棒，继续保持！",
    "漂亮，这一题完成得很棒！",
    "答对了，给自己点个赞！",
    "做得不错，继续加油！",
    "太棒了，下一题继续！",
]


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(cache: Path, filename: str) -> Path:
    path = cache / filename
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/{filename}"
    print(f"Downloading {filename}", flush=True)
    with urllib.request.urlopen(url, timeout=60) as response, temporary.open("wb") as output:
        shutil.copyfileobj(response, output, length=1024 * 1024)
    temporary.replace(path)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=ROOT / ".runtime" / "voice-model")
    parser.add_argument("--output", type=Path, default=ROOT / "public" / "audio" / "encouragement")
    parser.add_argument("--voice", choices=["zf_001", "zf_003"], default="zf_001")
    parser.add_argument("--speed", type=float, default=1.05)
    args = parser.parse_args()
    if not 0.7 <= args.speed <= 1.3:
        parser.error("--speed must be between 0.7 and 1.3")

    model_path = download(args.cache, MODEL_FILE)
    if digest(model_path) != MODEL_SHA256:
        raise RuntimeError("Model SHA-256 does not match the publisher's model card")
    config_path = download(args.cache, "config.json")
    voice_path = download(args.cache, f"voices/{args.voice}.pt")

    import numpy as np
    import soundfile as sf
    import torch
    from kokoro import KModel, KPipeline

    torch.manual_seed(42)
    torch.set_num_threads(4)
    model = KModel(repo_id=REPO, config=str(config_path), model=str(model_path)).to("cpu").eval()
    pipeline = KPipeline(lang_code="z", repo_id=REPO, model=model)
    sample_rate = 24000
    args.output.mkdir(parents=True, exist_ok=True)
    entries = []
    for index, text in enumerate(PHRASES, start=1):
        audio = np.concatenate([
            result.audio.cpu().numpy()
            for result in pipeline(text, voice=str(voice_path), speed=args.speed)
        ])
        if not np.isfinite(audio).all():
            raise RuntimeError("Model returned non-finite audio samples")
        audible = np.flatnonzero(np.abs(audio) > 0.006)
        if not len(audible):
            raise RuntimeError("Model returned silent audio")
        # Retain 80ms at each edge and normalize peak to -3dB, with no pitch changes.
        margin = int(sample_rate * 0.08)
        audio = audio[max(0, audible[0] - margin):min(len(audio), audible[-1] + margin + 1)]
        audio *= (10 ** (-3 / 20)) / float(np.max(np.abs(audio)))
        filename = f"correct-{index:02}.wav"
        path = args.output / filename
        sf.write(path, audio, sample_rate, subtype="PCM_16")
        decoded, decoded_rate = sf.read(path)
        duration = len(decoded) / decoded_rate
        rms = float(np.sqrt(np.mean(decoded ** 2)))
        if decoded_rate != sample_rate or not 0.5 < duration < 8 or rms < 0.01:
            raise RuntimeError(f"Decoded audio quality check failed: {filename}")
        entries.append({
            "file": filename,
            "text": text,
            "duration_seconds": round(duration, 3),
            "bytes": path.stat().st_size,
            "sha256": digest(path),
            "decoded_sample_rate": decoded_rate,
            "rms": round(rms, 5),
            "peak": round(float(np.max(np.abs(decoded))), 5),
        })
        print(f"Rendered {filename}: {duration:.2f}s; {text}", flush=True)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": "AI-generated speech, not a human recording",
        "model": REPO,
        "revision": REVISION,
        "model_sha256": MODEL_SHA256,
        "config_sha256": digest(config_path),
        "voice": args.voice,
        "voice_sha256": digest(voice_path),
        "model_license": "Apache-2.0",
        "source_url": f"https://huggingface.co/{REPO}/tree/{REVISION}",
        "model_card_url": f"https://huggingface.co/{REPO}",
        "language": "zh-CN",
        "sample_rate": sample_rate,
        "format": "WAV PCM signed 16-bit mono",
        "speed": args.speed,
        "seed": 42,
        "device": "cpu",
        "processing": "80ms edge padding retained; peak normalized to -3dB; no pitch modification",
        "dependencies": {name: importlib.metadata.version(name) for name in ["torch", "kokoro", "misaki", "soundfile", "transformers"]},
        "clips": entries,
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
