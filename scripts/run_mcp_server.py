#!/usr/bin/env python3
"""
Run the MCP server with the reorganized code structure.
"""

import sys
from pathlib import Path

# Add src to Python path
project_root = Path(__file__).resolve().parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# Run the MCP server directly
if __name__ == "__main__":
    import subprocess

    # Run the main server file directly
    server_path = project_root / "src" / "mcp" / "server.py"
    subprocess.run([sys.executable, str(server_path)])
