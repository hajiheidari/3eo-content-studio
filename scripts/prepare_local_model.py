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
MODEL_REPO = "Qwen/Qwen3-4B-GGUF"
MODEL_FILE = "Qwen3-4B-Q4_K_M.gguf"


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


def main():
    LOCAL.mkdir(exist_ok=True)
    (LOCAL / "models").mkdir(exist_ok=True)
    with httpx.Client(timeout=60) as client:
        archive = LOCAL / f"llama-{VERSION}.tar.gz"
        download(client, RUNTIME, archive, RUNTIME_SHA, 150 * 1024 * 1024)
        runtime_dir = LOCAL / "llama"
        runtime_dir.mkdir(exist_ok=True)
        with tarfile.open(archive) as bundle:
            bundle.extractall(runtime_dir, filter="data")
        # Pin the selected official repository revision, then obtain authoritative LFS SHA.
        response = client.get(f"https://huggingface.co/api/models/{MODEL_REPO}")
        response.raise_for_status()
        revision = response.json()["sha"]
        details = client.get(
            f"https://huggingface.co/api/models/{MODEL_REPO}/revision/{revision}",
            params={"blobs": "true"},
        )
        details.raise_for_status()
        model = next(
            entry for entry in details.json()["siblings"] if entry["rfilename"] == MODEL_FILE
        )
        checksum = model["lfs"]["sha256"]
        if len(checksum) != 64:
            raise RuntimeError("Model checksum unavailable")
        destination = LOCAL / "models" / MODEL_FILE
        download(
            client,
            f"https://huggingface.co/{MODEL_REPO}/resolve/{revision}/{MODEL_FILE}",
            destination,
            checksum,
            4 * 1024**3,
        )
        (LOCAL / "model-manifest.json").write_text(
            json.dumps(
                {
                    "repo": MODEL_REPO,
                    "revision": revision,
                    "file": MODEL_FILE,
                    "sha256": checksum,
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
