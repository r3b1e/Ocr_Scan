"""Run the extraction service: `python -m service [--host H] [--port P] [--env PATH]`."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import uvicorn

from config.settings import Settings
from service.api import create_app
from utils.logger import setup_logging


def main(argv: Sequence[str] | None = None) -> int:
    """Start uvicorn with the configured host and port."""
    parser = argparse.ArgumentParser(description="remainRX prescription extraction service")
    parser.add_argument("--host", default=None, help="bind address (overrides API_HOST)")
    parser.add_argument("--port", type=int, default=None, help="port (overrides API_PORT)")
    parser.add_argument("--env", type=Path, default=None, help="path to a .env file")
    args = parser.parse_args(argv)

    settings = Settings.load(env_path=args.env)
    settings.ensure_directories()
    logger = setup_logging(settings.logs_dir, settings.log_level)
    host = args.host or settings.api_host
    port = args.port or settings.api_port
    logger.info(
        "Starting extraction service on %s:%s (backend=%s)", host, port, settings.extractor_backend
    )
    uvicorn.run(create_app(settings), host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
