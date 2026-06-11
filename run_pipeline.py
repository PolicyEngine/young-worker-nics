"""Backwards-compatible shim: prefer `python -m young_worker_nics` or the
`young-worker-nics-build` console script."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from young_worker_nics.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
