"""Normalize a source distribution to deterministic TAR and gzip metadata."""

from __future__ import annotations

import argparse
import copy
import gzip
import io
import os
import tarfile
import tempfile
from pathlib import Path


def normalize_sdist(path: Path, epoch: int) -> None:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)

    entries: list[tuple[tarfile.TarInfo, bytes | None]] = []
    with tarfile.open(path, "r:gz") as source:
        for member in source.getmembers():
            if member.issym() or member.islnk():
                raise ValueError(f"links are forbidden in release sdist: {member.name}")
            payload = None
            if member.isfile():
                extracted = source.extractfile(member)
                if extracted is None:
                    raise ValueError(f"could not read sdist member: {member.name}")
                payload = extracted.read()
            entries.append((member, payload))

    with tempfile.TemporaryDirectory(prefix="kb-factory-sdist-", dir=path.parent) as raw:
        temp_dir = Path(raw)
        tar_path = temp_dir / "payload.tar"
        gzip_path = temp_dir / path.name
        with tarfile.open(tar_path, "w", format=tarfile.PAX_FORMAT) as target:
            for original, payload in sorted(entries, key=lambda item: item[0].name):
                member = copy.copy(original)
                member.mtime = epoch
                member.uid = 0
                member.gid = 0
                member.uname = ""
                member.gname = ""
                member.pax_headers = {}
                target.addfile(
                    member,
                    io.BytesIO(payload) if payload is not None else None,
                )
        with tar_path.open("rb") as source, gzip_path.open("wb") as destination:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                compresslevel=9,
                fileobj=destination,
                mtime=epoch,
            ) as compressed:
                while chunk := source.read(1024 * 1024):
                    compressed.write(chunk)
        os.replace(gzip_path, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--epoch", type=int, required=True)
    args = parser.parse_args()
    if args.epoch < 0:
        parser.error("--epoch must be non-negative")
    normalize_sdist(args.path, args.epoch)
    print(path := args.path.resolve())
    return 0 if path.is_file() else 1


if __name__ == "__main__":
    raise SystemExit(main())
