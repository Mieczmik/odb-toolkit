import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"


def load_config(path: Path) -> dict:
    with open(path) as f:
        cfg = yaml.safe_load(f)
    cfg['odb_path'] = str((ROOT / cfg['odb_path']).resolve())
    cfg.setdefault('abaqus_cmd', 'abaqus')
    cfg.setdefault('keep_data', False)
    cfg.setdefault('sources', 'ALL')
    return cfg


def run_step(cmd: list[str], label: str, expected_file: Path | None = None):
    """Run a subprocess, stream output, abort on failure."""
    print(f"\n{'='*60}")
    print(f"  [{label}] {' '.join(cmd)}")
    print(f"{'='*60}")
    # shell=True needed on Windows to resolve .bat/.cmd commands like 'abaqus'
    result = subprocess.run(cmd, cwd=str(ROOT), shell=True)
    if result.returncode != 0:
        print(f"\nERROR: {label} failed (exit code {result.returncode})")
        sys.exit(1)
    if expected_file and not expected_file.exists():
        print(f"\nERROR: {label} finished but expected output missing: {expected_file}")
        print("Check abaqus log files (*.log, *.rpy) for details.")
        sys.exit(1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config.yaml", help="Path to config YAML")
    args = p.parse_args()

    cfg = load_config(ROOT / args.config)

    # Resolve sources: list or "ALL"
    sources = cfg['sources']
    if isinstance(sources, list):
        sources_display = sources
    else:
        sources_display = "ALL"
        sources = "ALL"

    # Local temp dir for inter-process communication
    tmp = ROOT / ".tmp"
    tmp.mkdir(exist_ok=True)
    runtime = {
        "odb_path": cfg['odb_path'],
        "sources": sources,
        "extracted_path": str(tmp / "extracted.json"),
        "results_path": str(tmp / "results.json"),
    }
    runtime_path = tmp / "runtime.json"
    runtime_path.write_text(json.dumps(runtime, indent=2))

    extracted = Path(runtime['extracted_path'])
    results = Path(runtime['results_path'])

    print(f"ODB: {cfg['odb_path']}")
    print(f"Sources: {sources_display}")
    print(f"Keep data: {cfg['keep_data']}")

    # 1) Extract (abaqus python -- Py2)
    run_step(
        [cfg['abaqus_cmd'], "python", str(SRC / "extract.py"), str(runtime_path)],
        "1/3 extract",
        expected_file=extracted,
    )

    # 2) Compute custom fields (python3)
    run_step(
        [sys.executable, str(SRC / "compute.py"), str(runtime_path)],
        "2/3 compute",
        expected_file=results,
    )

    # 3) Inject (abaqus python -- Py2)
    run_step(
        [cfg['abaqus_cmd'], "python", str(SRC / "inject.py"), str(runtime_path)],
        "3/3 inject",
    )

    # Cleanup
    if cfg['keep_data']:
        print(f"\nIntermediate files kept in: {tmp}")
    else:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\nDone -- open ODB in CAE and select new fields.")


if __name__ == "__main__":
    main()