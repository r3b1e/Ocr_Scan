"""Entry point for the OCR Data Scanning Tool.

Usage:
    python main.py                # use .env / defaults
    python main.py --camera 1     # override the camera index
    python main.py --env path/to/.env
"""

from __future__ import annotations

import argparse
import sys
import tkinter as tk
from collections.abc import Sequence
from pathlib import Path
from tkinter import messagebox

from config.settings import Settings
from gui.app import OCRScannerApp
from utils.logger import setup_logging


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description="Real-time OCR data scanning tool")
    parser.add_argument("--camera", type=int, default=None, help="camera index (overrides .env)")
    parser.add_argument("--env", type=Path, default=None, help="path to a .env file")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="log verbosity (overrides .env)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Build the window and run the Tk main loop. Returns a process exit code."""
    args = parse_args(argv)
    settings = Settings.load(env_path=args.env)
    if args.camera is not None:
        settings.camera_index = max(0, args.camera)
    if args.log_level:
        settings.log_level = args.log_level
    try:
        settings.ensure_directories()
    except OSError as exc:
        print(
            f"Cannot create working directories under {settings.base_dir}: {exc}", file=sys.stderr
        )
        return 1
    logger = setup_logging(settings.logs_dir, settings.log_level)
    logger.info("Starting %s", OCRScannerApp.TITLE)

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        logger.exception("Tk could not open a window")
        print(f"Could not open a window: {exc}", file=sys.stderr)
        return 1

    try:
        app = OCRScannerApp(root, settings)
    except Exception as exc:
        logger.exception("The application failed to start")
        messagebox.showerror(
            OCRScannerApp.TITLE,
            f"The application could not start:\n\n{exc}\n\n"
            f"See {settings.logs_dir / 'app.log'} for details.",
        )
        root.destroy()
        return 1

    def report_callback_exception(exc_type: type, value: BaseException, traceback: object) -> None:
        logger.error("Unhandled error in a Tk callback", exc_info=(exc_type, value, traceback))
        try:
            app.console.insert("ERROR", f"Unexpected error: {value} (see logs/app.log)")
        except tk.TclError:
            pass

    root.report_callback_exception = report_callback_exception  # type: ignore[method-assign]
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.quit_app()
    logger.info("Exited cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
