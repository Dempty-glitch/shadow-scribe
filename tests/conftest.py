"""conftest.py — Backup path injection cho pytest.

pyproject.toml [tool.pytest.ini_options] pythonpath = ["."] đã handle việc này.
File này là safety net nếu pytest version cũ không đọc pyproject.toml.
"""
import sys
import pathlib

# Đảm bảo root của project nằm trong sys.path
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
