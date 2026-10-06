"""Assemble release artifacts into dist/: dataset, duckdb, SHA256SUMS."""

from __future__ import annotations

import hashlib
import shutil

from psd2_kpi_es import config

ARTIFACTS = [
    config.OBSERVATIONS_PARQUET,
    config.SOURCES_PARQUET,
    config.DUCKDB_PATH,
    config.REPORTS_DIR / "latest.md",
]


def main() -> None:
    config.DIST_DIR.mkdir(exist_ok=True)
    sums = []
    for src in ARTIFACTS:
        if not src.exists():
            print(f"missing: {src}")
            continue
        dst = config.DIST_DIR / src.name
        if src != dst:
            shutil.copy2(src, dst)
        digest = hashlib.sha256(dst.read_bytes()).hexdigest()
        sums.append(f"{digest}  {dst.name}")
        print(f"{dst.name}: {len(dst.read_bytes())} bytes")
    (config.DIST_DIR / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print("wrote dist/SHA256SUMS")


if __name__ == "__main__":
    main()
