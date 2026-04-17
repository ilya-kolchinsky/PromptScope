#!/usr/bin/env python3
"""
Main entry point for PromptScope application.

Run this script to start the web server.
"""

import os
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Load environment variables
from dotenv import load_dotenv

load_dotenv()

# Import and run server
from promptscope.api.server import app

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    print("=" * 60)
    print("🔍 PromptScope - Safe Multi-User LLM Chats")
    print("=" * 60)
    print(f"Starting server at http://{host}:{port}")
    print(f"LLM Provider: {os.getenv('LLM_PROVIDER', 'mock')}")
    print("=" * 60)

    uvicorn.run(app, host=host, port=port)
