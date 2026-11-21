"""CLI entry point for the optional offline household speaker experiment."""
import runpy
from pathlib import Path

if __name__ == "__main__":
    module = Path(__file__).resolve().parents[1] / "backend/app/family/speaker_model.py"
    runpy.run_path(str(module), run_name="__main__")
