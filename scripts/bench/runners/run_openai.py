# SPDX-License-Identifier: MIT
"""Thin wrapper around the OpenAI Agents SDK for `scripts/bench/run.sh`.

Reads a prompt from a file, optionally loads an instructions (system-prompt)
file for the treatment condition, runs an Agent against a specified model,
and writes the final output to stdout.

Usage:
    python run_openai.py --model gpt-5.4 --prompt-file prompt.txt
    python run_openai.py --model gpt-5.4 --prompt-file prompt.txt \
        --instructions-file .agent-style/codex-system-prompt.md

Exit codes:
    0 on success with non-empty output; 2 on CLI argument error; the SDK's
    native exit on API failure (stderr carries the message).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description="OpenAI Agents SDK runner for bench.")
    p.add_argument("--model", required=True, help="OpenAI model id (e.g. gpt-5.4)")
    p.add_argument("--prompt-file", required=True, help="Path to the prompt text file")
    p.add_argument(
        "--instructions-file",
        default=None,
        help="Optional system-prompt file; present for treatment, absent for baseline",
    )
    args = p.parse_args()

    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    instructions: str | None = None
    if args.instructions_file:
        instructions = Path(args.instructions_file).read_text(encoding="utf-8")

    # Imported after arg parsing so `--help` works without the SDK installed.
    from agents import Agent, Runner

    agent = Agent(
        name="bench-writer",
        model=args.model,
        instructions=instructions,
    )
    result = Runner.run_sync(agent, prompt)
    sys.stdout.write(result.final_output or "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
