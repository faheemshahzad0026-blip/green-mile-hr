import sys
from pathlib import Path

# cPanel Passenger entrypoint
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app

application = create_app()
