"""Offline, one-to-one speaker comparison for the LivingMind family demo."""
import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path


MODEL_FILES = ["embedding_model.ckpt", "hyperparams.yaml", "classifier.ckpt",
               "mean_var_norm_emb.ckpt", "label_encoder.txt"]


def load_encoder(model_dir, scratch):
    from speechbrain.inference.speaker import SpeakerRecognition

    missing = [name for name in MODEL_FILES if not (model_dir / name).is_file()]
    if missing:
        raise ValueError("Incomplete local model: " + ", ".join(missing))
    return SpeakerRecognition.from_hparams(
        source=str(model_dir), savedir=scratch,
        overrides={"pretrained_path": str(model_dir)},
        run_opts={"device": "cpu"},
    )


def model_signature(model_dir):
    digest = hashlib.sha256()
    for name in MODEL_FILES:
        with (model_dir / name).open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def embedding(encoder, audio):
    import soundfile as sf
    import torch
    from torchaudio.functional import resample

    with sf.SoundFile(audio) as clip:
        if not 1 <= clip.frames / clip.samplerate <= 30:
            raise ValueError(f"{audio}: provide a 1–30 second spoken clip")
        rate = clip.samplerate
        waveform = torch.from_numpy(clip.read(dtype="float32", always_2d=True)).mean(dim=1)
    if not torch.isfinite(waveform).all() or waveform.square().mean() < 1e-7:
        raise ValueError(f"{audio}: input is silent or invalid")
    if rate != 16000:
        waveform = resample(waveform, rate, 16000)
    with torch.inference_mode():
        encoded = encoder.encode_batch(waveform.unsqueeze(0)).flatten()
        if not torch.isfinite(encoded).all() or encoded.norm() < 1e-8:
            raise ValueError(f"{audio}: unusable embedding")
        return encoded / encoded.norm()


def compare_template(path, sample, signature):
    import torch

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("model_sha256") != signature:
        raise ValueError(f"{path}: template belongs to a different model")
    reference = torch.tensor(data.get("embedding", []), dtype=torch.float32)
    if reference.shape != sample.shape or not torch.isfinite(reference).all() or reference.norm() < 1e-8:
        raise ValueError(f"{path}: invalid enrollment template")
    similarity = float(torch.nn.functional.cosine_similarity(reference, sample, dim=0).clamp(-1, 1))
    if not math.isfinite(similarity):
        raise ValueError(f"{path}: invalid similarity")
    return similarity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path, help="Local ECAPA model directory")
    commands = parser.add_subparsers(dest="command", required=True)
    enroll = commands.add_parser("enroll", help="Create a reference template from given clips")
    enroll.add_argument("template", type=Path)
    enroll.add_argument("clips", type=Path, nargs="+")
    verify = commands.add_parser("verify", help="Compare one recording to an enrolled template")
    verify.add_argument("template", type=Path)
    verify.add_argument("clip", type=Path)
    verify.add_argument("--threshold", type=float, default=0.25)
    identify = commands.add_parser("identify", help="Compare one recording to multiple local templates")
    identify.add_argument("clip", type=Path)
    identify.add_argument("templates", type=Path, nargs="+", help="Distinct names identify household profiles")
    identify.add_argument("--threshold", type=float, default=0.25)
    identify.add_argument("--margin", type=float, default=0.10, help="Minimum lead over the runner-up")
    args = parser.parse_args()
    if args.command != "enroll" and not -1 <= args.threshold <= 1:
        parser.error("--threshold must be in [-1, 1]")
    if args.command == "identify":
        if not 0 < args.margin <= 2:
            parser.error("--margin must be in (0, 2]")
        if len(args.templates) < 2 or len({p.stem for p in args.templates}) != len(args.templates):
            parser.error("identify needs at least two distinct template names")

    os.environ["HF_HUB_OFFLINE"] = "1"
    import torch

    model_dir = args.model.resolve()
    with tempfile.TemporaryDirectory(prefix="livingmind-ecapa-") as scratch:
        encoder = load_encoder(model_dir, scratch)
        signature = model_signature(model_dir)
        if args.command == "enroll":
            centroid = torch.stack([embedding(encoder, path) for path in args.clips]).mean(dim=0)
            if centroid.norm() < 1e-8:
                raise ValueError("Enrollment clips produced a degenerate template")
            data = {"model_sha256": signature, "clips": len(args.clips),
                    "embedding": (centroid / centroid.norm()).tolist()}
            # Refuse to overwrite prior enrollment. Embeddings stay local to the operator.
            fd = os.open(args.template, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, allow_nan=False)
            result = {"enrolled": True, "clips": len(args.clips)}
        elif args.command == "verify":
            sample = embedding(encoder, args.clip)
            similarity = compare_template(args.template, sample, signature)
            result = {"cosine_similarity": round(similarity, 6), "threshold": args.threshold,
                      "comparison": "match" if similarity > args.threshold else "no-match",
                      "device_authorized": False}
        else:
            sample = embedding(encoder, args.clip)
            ranked = sorted(((compare_template(path, sample, signature), path.stem) for path in args.templates),
                            reverse=True)
            top, runner_up = ranked[:2]
            sufficient = top[0] > args.threshold and top[0] - runner_up[0] >= args.margin
            result = {"candidate": top[1] if sufficient else None,
                      "comparison": "candidate" if sufficient else "unknown",
                      "scores": {name: round(score, 6) for score, name in ranked},
                      "threshold": args.threshold, "required_margin": args.margin, "device_authorized": False}
        print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, TypeError, OSError, RuntimeError, ImportError) as exc:
        sys.exit(f"Speaker experiment could not complete: {exc}")
