"""Create a clean, self-contained source release ZIP using only stdlib."""
from __future__ import annotations

import argparse
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
EXCLUDED_DIRS = {"__pycache__", ".pytest_cache", ".mverify", ".mverify-validation", ".git", "build", "dist"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".sqlite3", ".db", ".log"}


def package(destination: Path) -> dict:
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    prefix = f"Mverify_{VERSION}/"
    count = 0
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(ROOT.rglob("*")):
            if not path.is_file() or any(part in EXCLUDED_DIRS or part.startswith(".venv") for part in path.relative_to(ROOT).parts):
                continue
            relative = path.relative_to(ROOT)
            if path.suffix.lower() in EXCLUDED_SUFFIXES or path.name in {"Thumbs.db", ".DS_Store"}:
                continue
            if path.name == ".env":
                continue
            archive.write(path, prefix + relative.as_posix())
            count += 1
    with zipfile.ZipFile(destination, "r") as archive:
        names = archive.namelist()
        bad = [name for name in names if any(f"/{directory}/" in name for directory in EXCLUDED_DIRS)
               or name.lower().endswith(tuple(EXCLUDED_SUFFIXES))]
        required = [prefix + "VERSION", prefix + "README.md", prefix + "DEPLOYMENT_v0.16.0.md",
                    prefix + "tools/remote_validate.py", prefix + "tests/fixtures/rtl/wrr_contract/pcie_wrr_arbiter.sv"]
        missing = [name for name in required if name not in names]
        if VERSION != "0.16.0" or bad or missing:
            raise RuntimeError(f"Release archive validation failed: version={VERSION}, bad={bad}, missing={missing}")
    return {"archive": str(destination), "version": VERSION, "entries": count,
            "size_bytes": destination.stat().st_size, "excluded_runtime_artifacts": True,
            "required_files_present": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", nargs="?", type=Path,
                        default=ROOT.parent / f"Mverify_{VERSION}_Mcore_Centric_Engineering_Intelligence.zip")
    args = parser.parse_args()
    print(package(args.destination))


if __name__ == "__main__":
    main()
