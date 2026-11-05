"""Parallel download of the faster-whisper-small preview model.bin."""

from __future__ import annotations

import concurrent.futures
import hashlib
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

URL = sys.argv[1] if len(sys.argv) > 1 else "https://huggingface.co/Systran/faster-whisper-small/resolve/main/model.bin"
EXPECTED_SIZE = int(sys.argv[2]) if len(sys.argv) > 2 else 483_546_902
EXPECTED_SHA256 = sys.argv[3] if len(sys.argv) > 3 else "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671"
ROOT = Path(__file__).resolve().parents[1]
OUT = sys.argv[4] if len(sys.argv) > 4 else str(ROOT / "models" / "faster-whisper-small" / "model.bin")
CHUNK = 4 * 1024 * 1024
THREADS = 24

lock = threading.Lock()
done = 0
started = time.time()


def fetch(start: int, end: int) -> bytes:
    last = None
    for attempt in range(6):
        try:
            req = urllib.request.Request(URL, headers={"Range": f"bytes={start}-{end}"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                if resp.status != 206:
                    raise RuntimeError(f"HTTP {resp.status}")
                data = resp.read()
            if len(data) != end - start + 1:
                raise RuntimeError(f"short read {len(data)}")
            return data
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"chunk {start}-{end}: {last}")


def worker(index: int) -> None:
    global done
    start = index * CHUNK
    end = min(start + CHUNK, EXPECTED_SIZE) - 1
    data = fetch(start, end)
    with open(OUT, "r+b") as f:
        f.seek(start)
        f.write(data)
    with lock:
        done += len(data)
        if index % 20 == 0 or done == EXPECTED_SIZE:
            print(
                f"{done / 1e6:.0f}/{EXPECTED_SIZE / 1e6:.0f} MB "
                f"({done / EXPECTED_SIZE * 100:.0f}%) "
                f"{done / 1e6 / max(time.time() - started, 1):.2f} MB/s",
                flush=True,
            )


def main() -> int:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "wb") as f:
        f.truncate(EXPECTED_SIZE)
    count = (EXPECTED_SIZE + CHUNK - 1) // CHUNK
    with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as pool:
        list(pool.map(worker, range(count)))
    h = hashlib.sha256()
    with open(OUT, "rb") as f:
        while True:
            block = f.read(16 * 1024 * 1024)
            if not block:
                break
            h.update(block)
    print("sha256", h.hexdigest())
    if h.hexdigest() != EXPECTED_SHA256:
        print("SHA256 mismatch", file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
