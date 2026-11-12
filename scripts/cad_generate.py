#!/usr/bin/env -S uv run --extra cad python
"""Run via uv run --extra cad python scripts/cad_generate.py."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mechanical_video_next.cad import main
main()
