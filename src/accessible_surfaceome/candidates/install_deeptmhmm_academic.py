"""Install DeepTMHMM Academic v1.0 with a uv-managed environment.

This script does not download DeepTMHMM itself; users must provide either:
- a local ZIP archive (e.g., ``DeepTMHMM-Academic-License-v1.0.zip``), or
- a local extracted directory.

The installer performs three reproducible steps:
1. Materialize the package under ``data/external/deeptmhmm/``.
2. Create/update ``.venv-deeptmhmm`` via ``uv`` and install pinned dependencies.
3. Apply a small matplotlib style compatibility patch required on modern stacks.

A machine-readable install traceability manifest is written to:
``data/external/deeptmhmm/install_traceability.json``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from accessible_surfaceome.candidates.traceability import sha256_file, utc_now_iso
from accessible_surfaceome.paths import (
    DATA_EXTERNAL_DIR,
    REPO_ROOT,
    relative_to_repo as _relative_to_repo,
)

DATASET = "DeepTMHMM_Academic_License_v1.0"
DEFAULT_SOURCE_URL = "https://dtu.biolib.com/DeepTMHMM/"
DEFAULT_INSTALL_ROOT = DATA_EXTERNAL_DIR / "deeptmhmm"
DEFAULT_PACKAGE_DIR = DEFAULT_INSTALL_ROOT / "DeepTMHMM-Academic-License-v1.0"
DEFAULT_MANIFEST = DEFAULT_INSTALL_ROOT / "install_traceability.json"
DEFAULT_VENV = REPO_ROOT / ".venv-deeptmhmm"
REQUIREMENTS_FILE = Path(__file__).with_name("deeptmhmm_uv_requirements.txt")

STYLE_LINE = "    plt.style.use('seaborn-whitegrid')\n"
STYLE_PATCH = (
    "    try:\n"
    "        plt.style.use('seaborn-whitegrid')\n"
    "    except OSError:\n"
    "        if 'seaborn-v0_8-whitegrid' in plt.style.available:\n"
    "            plt.style.use('seaborn-v0_8-whitegrid')\n"
    "        else:\n"
    "            plt.style.use('default')\n"
)


relative_to_repo = _relative_to_repo


def run_cmd(cmd: list[str], *, cwd: Path | None = None) -> None:
    """Run a command and stream output."""
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def find_uv() -> str:
    """Locate uv executable or fail with a clear message."""
    uv_bin = shutil.which("uv")
    if uv_bin is None:
        raise RuntimeError("uv is required but was not found on PATH")
    return uv_bin


def build_record(
    *,
    local_path: Path,
    source_url: str,
    status: str,
    note: str,
    include_sha: bool = True,
) -> dict[str, Any]:
    """Build one traceability record."""
    size_bytes: int | None = None
    sha256: str = ""
    if local_path.exists() and local_path.is_file():
        size_bytes = int(local_path.stat().st_size)
        sha256 = sha256_file(local_path) if include_sha else ""

    record: dict[str, Any] = {
        "dataset": DATASET,
        "source_url": source_url,
        "local_path": relative_to_repo(local_path),
        "captured_at_utc": utc_now_iso(),
        "status": status,
        "note": note,
        "size_bytes": size_bytes,
        "sha256": sha256,
    }
    return record


def detect_extracted_root(extract_dir: Path) -> Path:
    """Detect package root after ZIP extraction."""
    preferred = extract_dir / "DeepTMHMM-Academic-License-v1.0"
    if (preferred / "predict.py").exists():
        return preferred

    candidates: list[Path] = []
    for child in extract_dir.iterdir():
        if child.is_dir() and (child / "predict.py").exists():
            candidates.append(child)

    if len(candidates) == 1:
        return candidates[0]
    raise RuntimeError(
        "Could not detect DeepTMHMM package root after extraction; "
        "expected a directory containing predict.py"
    )


def materialize_package(source: Path, package_dir: Path, force: bool) -> str:
    """Copy/extract package to package_dir and return status."""
    if package_dir.exists():
        if force:
            shutil.rmtree(package_dir)
        else:
            return "existing"

    package_dir.parent.mkdir(parents=True, exist_ok=True)

    if source.is_dir():
        if not (source / "predict.py").exists():
            raise RuntimeError(f"Source directory missing predict.py: {source}")
        shutil.copytree(source, package_dir)
        return "downloaded"

    if not source.is_file() or source.suffix.lower() != ".zip":
        raise RuntimeError("--source must be a DeepTMHMM directory or .zip archive")

    tmp_extract = package_dir.parent / ".tmp_deeptmhmm_extract"
    if tmp_extract.exists():
        shutil.rmtree(tmp_extract)
    tmp_extract.mkdir(parents=True, exist_ok=False)

    with zipfile.ZipFile(source, "r") as zf:
        zf.extractall(tmp_extract)

    extracted_root = detect_extracted_root(tmp_extract)
    shutil.move(str(extracted_root), str(package_dir))
    shutil.rmtree(tmp_extract)
    return "downloaded"


def patch_predict_style(predict_py: Path) -> bool:
    """Patch legacy seaborn style reference for modern matplotlib.

    Returns True if a patch was applied, False if no change was needed.
    """
    content = predict_py.read_text(encoding="utf-8")
    if "seaborn-v0_8-whitegrid" in content:
        return False
    if STYLE_LINE not in content:
        raise RuntimeError(f"Expected style line not found in {predict_py}")
    predict_py.write_text(content.replace(STYLE_LINE, STYLE_PATCH, 1), encoding="utf-8")
    return True


def install_uv_env(uv_bin: str, venv_path: Path) -> Path:
    """Create/update uv environment and install pinned dependencies."""
    run_cmd([uv_bin, "venv", str(venv_path), "--python", "3.11"], cwd=REPO_ROOT)
    python_bin = venv_path / "bin" / "python"
    if not python_bin.exists():
        raise RuntimeError(f"Expected python executable not found: {python_bin}")

    run_cmd(
        [
            uv_bin,
            "pip",
            "install",
            "--python",
            str(python_bin),
            "wheel",
            "Cython==0.29.37",
            "pkgconfig==1.5.5",
        ],
        cwd=REPO_ROOT,
    )
    run_cmd(
        [
            uv_bin,
            "pip",
            "install",
            "--python",
            str(python_bin),
            "-r",
            str(REQUIREMENTS_FILE),
        ],
        cwd=REPO_ROOT,
    )
    return python_bin


def run_smoke_test(python_bin: Path, package_dir: Path, output_dir: Path) -> None:
    """Run DeepTMHMM on bundled sample FASTA to verify installation."""
    if output_dir.exists():
        shutil.rmtree(output_dir)
    run_cmd(
        [
            str(python_bin),
            "predict.py",
            "--fasta",
            "sample.fasta",
            "--output-dir",
            str(output_dir),
        ],
        cwd=package_dir,
    )


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    """Write install manifest as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """Parse command line args."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to DeepTMHMM-Academic-License-v1.0.zip or extracted directory.",
    )
    parser.add_argument(
        "--source-url",
        default=DEFAULT_SOURCE_URL,
        help="Reference source URL for traceability manifest.",
    )
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--venv-path", type=Path, default=DEFAULT_VENV)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-materialize package directory even if it already exists.",
    )
    parser.add_argument(
        "--skip-env-install",
        action="store_true",
        help="Skip uv environment creation/dependency installation.",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Run predict.py on sample.fasta after setup.",
    )
    parser.add_argument(
        "--smoke-test-output-dir",
        type=Path,
        default=Path("/tmp/deeptmhmm_uv_smoketest"),
        help="Output directory used when --smoke-test is enabled.",
    )
    return parser.parse_args()


def main() -> None:
    """Install DeepTMHMM package and uv runtime."""
    args = parse_args()

    source = args.source.expanduser().resolve()
    package_dir = args.package_dir.expanduser().resolve()
    manifest = args.manifest.expanduser().resolve()
    venv_path = args.venv_path.expanduser().resolve()

    if not source.exists():
        raise RuntimeError(f"Source path does not exist: {source}")

    source_record = build_record(
        local_path=source,
        source_url=args.source_url,
        status="existing",
        note="User-provided DeepTMHMM package source",
    )

    install_status = materialize_package(source=source, package_dir=package_dir, force=args.force)

    predict_py = package_dir / "predict.py"
    if not predict_py.exists():
        raise RuntimeError(f"Expected predict.py not found in {package_dir}")
    patched = patch_predict_style(predict_py)

    # Record hash/size after patching so manifest reflects final on-disk artifact.
    package_record = build_record(
        local_path=package_dir / "predict.py",
        source_url=args.source_url,
        status=install_status,
        note="Materialized DeepTMHMM package entrypoint",
    )

    python_bin: Path | None = None
    if not args.skip_env_install:
        uv_bin = find_uv()
        python_bin = install_uv_env(uv_bin=uv_bin, venv_path=venv_path)

    smoke_test_status = "skipped"
    if args.smoke_test:
        if python_bin is None:
            python_bin = venv_path / "bin" / "python"
            if not python_bin.exists():
                raise RuntimeError(
                    "--smoke-test requires a Python executable at --venv-path/bin/python "
                    "or omit --skip-env-install"
                )
        run_smoke_test(
            python_bin=python_bin,
            package_dir=package_dir,
            output_dir=args.smoke_test_output_dir.expanduser().resolve(),
        )
        smoke_test_status = "passed"

    manifest_payload: dict[str, Any] = {
        "dataset": DATASET,
        "generated_at_utc": utc_now_iso(),
        "script": Path(__file__).as_posix(),
        "requirements_file": relative_to_repo(REQUIREMENTS_FILE),
        "records": [source_record, package_record],
        "extras": {
            "source_url": args.source_url,
            "package_dir": relative_to_repo(package_dir),
            "venv_path": relative_to_repo(venv_path),
            "predict_style_patch_applied": patched,
            "smoke_test": smoke_test_status,
        },
    }
    write_manifest(manifest, manifest_payload)

    print(f"Package directory: {package_dir}")
    print(f"Venv path: {venv_path}")
    print(f"Manifest: {manifest}")
    if python_bin is not None:
        print(
            "Run command:\n"
            f"  {python_bin} {package_dir / 'predict.py'} --fasta /abs/input.fasta --output-dir /abs/output_dir"
        )


if __name__ == "__main__":
    main()
