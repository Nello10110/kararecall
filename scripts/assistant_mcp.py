#!/usr/bin/env python3
"""Absolute-path entry point for desktop MCP clients, from any working directory."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kararecall.mcp import main

if __name__ == '__main__':
    main()
