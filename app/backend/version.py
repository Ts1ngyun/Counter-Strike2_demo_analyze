"""Distribution version, independent of parser/module algorithm versions."""
from pathlib import Path

APP_VERSION = (Path(__file__).resolve().parents[1] / 'VERSION').read_text(encoding='utf-8').strip()
