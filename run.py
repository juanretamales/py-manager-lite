import os
import sys
from pathlib import Path

# Ensure project root is at the front of sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import flet as ft
from app.db.session import init_db
from app.main import main

if __name__ == "__main__":
    init_db()
    ft.run(main)
