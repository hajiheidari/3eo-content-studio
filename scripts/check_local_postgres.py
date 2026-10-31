"""Run the suite against a temporary, loopback-only PostgreSQL instance, then stop it.

Use existing PostgreSQL binaries; this script never installs software or changes services.
Example: uv run --frozen python scripts/check_local_postgres.py --postgres-bin /path/to/bin
"""

import argparse
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres-bin", type=Path, required=True)
    args = parser.parse_args()
    binaries = args.postgres_bin.resolve()
    for name in ("initdb", "pg_ctl", "createdb", "postgres"):
        if not (binaries / name).is_file():
            parser.error(f"Missing PostgreSQL executable: {name}")
    root = Path(__file__).resolve().parents[1]
    cache = root / ".pytest_cache"
    cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="postgres-", dir=cache) as folder:
        data = Path(folder)
        with socket.socket() as candidate:
            candidate.bind(("127.0.0.1", 0))
            port = candidate.getsockname()[1]
        def command(name, *arguments):
            return [str(binaries / name), *map(str, arguments)]
        try:
            subprocess.run(command("initdb", "-D", data, "-U", "studio_test", "-A", "trust",
                                   "--no-locale", "-E", "UTF8"), check=True,
                           stdout=subprocess.DEVNULL)
            subprocess.run(command("postgres", "--version"), check=True)
            subprocess.run(command("pg_ctl", "-D", data, "-l", data / "server.log", "-o",
                                   f"-h 127.0.0.1 -p {port} -k '' -c max_connections=20",
                                   "-w", "start"), check=True, stdout=subprocess.DEVNULL)
            subprocess.run(command("createdb", "-h", "127.0.0.1", "-p", port,
                                   "-U", "studio_test", "studio_test"), check=True)
            env = dict(os.environ, STUDIO_TEST_POSTGRES_URL=(
                f"postgresql+psycopg://studio_test@127.0.0.1:{port}/studio_test"))
            result = subprocess.run([sys.executable, "-m", "pytest", "-q"], env=env, cwd=root)
            return result.returncode
        finally:
            status = subprocess.run(command("pg_ctl", "-D", data, "status"),
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if status.returncode == 0:
                subprocess.run(command("pg_ctl", "-D", data, "-w", "stop", "-m", "fast"),
                               check=True, stdout=subprocess.DEVNULL)
                print("Temporary PostgreSQL stopped", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
