#!/usr/bin/env python3
"""
Main entry point for Specbook Agent
Natural Language Interface for Architectural Product Specifications
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import and run CLI
from cli.chat_interface import app

if __name__ == "__main__":
    app()