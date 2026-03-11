from __future__ import annotations

import pathlib
import sys
import warnings

ROOT_DIR = pathlib.Path(__file__).resolve().parent

warnings.filterwarnings(
    "ignore",
    message=r"urllib3 v2 only supports OpenSSL 1\.1\.1\+",
    category=Warning,
)

sys.argv = [
    "streamlit",
    "run",
    str(ROOT_DIR / "streamlit_app.py"),
    *sys.argv[1:],
]

from streamlit.web.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
