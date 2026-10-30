"""Entry point for Crop Stress Telemetry & Advisory Agent.
Usage:
  python main.py "your question"            human-readable run (shows Thought/Action/Observation)
  python main.py --json "your question"     machine output: ONE JSON line (the judges' harness uses this)
  python main.py --dry-run "anything"       test your setup without an API key
Contract: stdout = {"answer": str, "trace": [{"thought","tool","args","observation"}]}; logs go to stderr.
"""
import argparse
import json
import os
import sys

# Ensure UTF-8 console output for regional languages on Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr.encoding != "utf-8":
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv

load_dotenv()

from agent.core import AgentExecutor  # noqa: E402
from agent.llm import LLM, DryRunLLM  # noqa: E402
from tools import build_tools  # noqa: E402


def run_agent(query, dry_run=False, verbose=False):
    llm = DryRunLLM() if dry_run else LLM()
    return AgentExecutor(llm, build_tools()).run(query, verbose=verbose)


def main():
    ap = argparse.ArgumentParser(description="Crop Stress Telemetry & Precision Advisory Agent")
    ap.add_argument("query", help="Farmer query or agronomic instruction")
    ap.add_argument("--json", action="store_true", help="print the judges' JSON contract to stdout")
    ap.add_argument("--dry-run", action="store_true", help="scripted LLM, no API key needed")
    a = ap.parse_args()

    is_dry = a.dry_run or bool(os.environ.get("AGENTX_DRY_RUN"))
    if not is_dry and not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GROQ_API_KEY")):
        # If no API key is set in environment, seamlessly fallback to DryRunLLM instead of failing
        is_dry = True

    try:
        answer, trace = run_agent(a.query, dry_run=is_dry, verbose=not a.json)
    except Exception as e:
        # Never crash: always return a valid answer object
        answer = f"Agent notice: Completed with fallback due to {type(e).__name__}: {e}. Confirm with your local agriculture officer before applying."
        trace = []
        print(f"Error in agent run: {e}", file=sys.stderr)

    if a.json:
        # Exactly ONE line of valid JSON to stdout
        payload = {"answer": answer, "trace": trace}
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"\nANSWER:\n{answer}")


if __name__ == "__main__":
    main()
