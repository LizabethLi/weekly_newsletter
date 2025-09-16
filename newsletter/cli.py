"""Command line interface for the newsletter workflow."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Sequence

from .models import NewsletterConfig
from .renderer import render_markdown
from .workflow import run_workflow


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate an AI newsletter from a TXT (URLs per line) or CSV input file."
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to the input file (TXT with one URL per line, or CSV with title/url columns).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("newsletter.md"),
        help="Destination markdown file for the generated newsletter.",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="Request timeout for fetching articles (seconds).")
    parser.add_argument("--retries", type=int, default=2, help="Maximum number of retries for network requests.")
    parser.add_argument(
        "--max-words",
        type=int,
        default=100,
        help="Maximum number of words allowed in each recommendation blurb.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity level.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s: %(message)s")

    config = NewsletterConfig(
        input_path=args.input_file,
        output_path=args.output,
        request_timeout=args.timeout,
        max_retries=args.retries,
        max_recommendation_words=args.max_words,
    )

    output = run_workflow(config)
    markdown = render_markdown(output)
    args.output.write_text(markdown, encoding="utf-8")
    logging.info("Newsletter written to %s", args.output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
