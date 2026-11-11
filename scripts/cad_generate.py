#!/usr/bin/env python3
"""Run with a Python environment containing build123d and trimesh."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mechanical_video_next.cad import main
main()
