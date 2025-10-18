import os
import sys

BASE_DIR = os.path.dirname(__file__)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fstore_app.app import app as application  # noqa: E402
