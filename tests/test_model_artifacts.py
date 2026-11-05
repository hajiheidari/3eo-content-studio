import hashlib
import runpy
from pathlib import Path

import httpx
import pytest

DOWNLOAD = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/prepare_local_model.py")
)["download"]


def test_download_requires_checksum_and_cleans_partial(tmp_path):
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"corrupted"))
    )
    target = tmp_path / "model.gguf"
    with pytest.raises(RuntimeError, match="Checksum"):
        DOWNLOAD(
            client,
            "https://huggingface.co/test",
            target,
            hashlib.sha256(b"expected").hexdigest(),
            1000,
        )
    assert not target.exists() and not target.with_suffix(".gguf.partial").exists()


def test_verified_artifact_reused_without_network(tmp_path):
    target = tmp_path / "model.gguf"
    target.write_bytes(b"verified")

    def unexpected(request):
        pytest.fail("Valid artifact must be reused")

    client = httpx.Client(transport=httpx.MockTransport(unexpected))
    DOWNLOAD(
        client, "https://huggingface.co/test", target, hashlib.sha256(b"verified").hexdigest(), 1000
    )
    assert target.read_bytes() == b"verified"


def test_repeated_runtime_install_never_rewrites_mapped_files(tmp_path):
    import io
    import tarfile

    namespace = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/prepare_local_model.py")
    )
    extract = namespace["extract_runtime"]
    archive = tmp_path / "runtime.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        info = tarfile.TarInfo("runtime/libggml.so")
        info.size = len(b"original")
        bundle.addfile(info, io.BytesIO(b"original"))
    destination = tmp_path / "installed"
    extract(archive, destination)
    library = destination / "runtime/libggml.so"
    inode, modified = library.stat().st_ino, library.stat().st_mtime_ns
    extract(archive, destination)
    assert (library.stat().st_ino, library.stat().st_mtime_ns) == (inode, modified)
    library.write_bytes(b"corrupt")
    with pytest.raises(RuntimeError, match="stop its process"):
        extract(archive, destination)
    assert library.read_bytes() == b"corrupt"
