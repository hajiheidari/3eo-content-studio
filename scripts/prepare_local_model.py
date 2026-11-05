"""Explicit free CPU runtime/model preparation; no paid calls or secret requirements.

Run with .venv/bin/python scripts/prepare_local_model.py. TLS, checksums and model
revision pinning are mandatory. Artifacts are kept in ignored .local/, never Git.
"""

import hashlib
import json
import tarfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
VERSION = "b12129"
RUNTIME = f"https://github.com/ggml-org/llama.cpp/releases/download/{VERSION}/llama-{VERSION}-bin-ubuntu-x64.tar.gz"
RUNTIME_SHA = "a6463c212b8db508cb897675159cccf7f1f50d9380df00dc33a77e2863feff23"
MODEL_REPO = "Qwen/Qwen2.5-14B-Instruct-GGUF"
MODEL_REVISION = "b466e1f8c07172155743e8e1307507d8a4f91fbd"
MODEL_FILES = [
    (
        "qwen2.5-14b-instruct-q4_k_m-00001-of-00003.gguf",
        "a09ea5e7b1eafb1b30b241726c3cc3c905c96f14ad41e246ffa5f44e53904f68",
    ),
    (
        "qwen2.5-14b-instruct-q4_k_m-00002-of-00003.gguf",
        "21b9457d079680d284e90ef69607c4b2d8ef64a09d4729cb7b5e1357bdba41ae",
    ),
    (
        "qwen2.5-14b-instruct-q4_k_m-00003-of-00003.gguf",
        "c8d37006760a387a35216e070e6664d7da927f10be8eb870fef2e3d4833d9976",
    ),
]


def download(client, url, destination, expected, max_bytes):
    if (
        destination.exists()
        and hashlib.file_digest(destination.open("rb"), "sha256").hexdigest() == expected
    ):
        return
    temporary = destination.with_suffix(destination.suffix + ".partial")
    digest, size = hashlib.sha256(), 0
    try:
        with client.stream("GET", url, follow_redirects=True) as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        raise RuntimeError("Artifact exceeds expected resource limit")
                    digest.update(chunk)
                    output.write(chunk)
        if digest.hexdigest() != expected:
            raise RuntimeError("Checksum mismatch; artifact will not be used")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def extract_runtime(archive, runtime_dir):
    """Never replace native libraries while a server may have them memory-mapped."""
    runtime_dir.mkdir(exist_ok=True)
    with tarfile.open(archive) as bundle:
        files = [member for member in bundle.getmembers() if member.isfile()]
        intact = True
        for member in files:
            target = runtime_dir / member.name
            if not target.resolve().is_relative_to(runtime_dir.resolve()):
                raise RuntimeError("Unsafe runtime archive path")
            if not target.is_file():
                intact = False
                break
            with target.open("rb") as installed, bundle.extractfile(member) as original:
                if (
                    hashlib.file_digest(installed, "sha256").digest()
                    != hashlib.file_digest(original, "sha256").digest()
                ):
                    intact = False
                    break
        if intact:
            return
        if any(runtime_dir.iterdir()):
            raise RuntimeError(
                "Existing runtime differs; stop its process and move that runtime directory aside before repair"
            )
        bundle.extractall(runtime_dir, filter="data")


def main():
    LOCAL.mkdir(exist_ok=True)
    (LOCAL / "models").mkdir(exist_ok=True)
    with httpx.Client(timeout=60) as client:
        archive = LOCAL / f"llama-{VERSION}.tar.gz"
        download(client, RUNTIME, archive, RUNTIME_SHA, 150 * 1024 * 1024)
        runtime_dir = LOCAL / "llama"
        extract_runtime(archive, runtime_dir)
        # Official repository revision and every LFS SHA are pinned and verified.
        for name, checksum in MODEL_FILES:
            download(
                client,
                f"https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/{name}",
                LOCAL / "models" / name,
                checksum,
                5 * 1024**3,
            )
        (LOCAL / "model-manifest.json").write_text(
            json.dumps(
                {
                    "repo": MODEL_REPO,
                    "revision": MODEL_REVISION,
                    "files": [{"file": name, "sha256": sha} for name, sha in MODEL_FILES],
                    "runtime_version": VERSION,
                    "runtime_sha256": RUNTIME_SHA,
                },
                indent=2,
            )
        )
        print("Verified CPU runtime and Qwen model ready in ignored .local/")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPError:
        raise SystemExit(
            "Download unavailable. Review cloud network settings for GitHub/Hugging Face/CDNs; TLS remains verified. No model readiness is claimed."
        ) from None
