"""
Configuration file for pytest.
"""
import sys
import os

# Add the project root to Python path so tests can import modules
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
