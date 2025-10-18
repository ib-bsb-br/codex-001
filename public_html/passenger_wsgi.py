import sys
import os

# Add the app's directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fstore_app'))

# Import the application object
from app import app as application