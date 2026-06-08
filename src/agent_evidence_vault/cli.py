"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List

from . import __version__
from .api import collect_vault, load_manifest, verify_manifest
from .config import explain_config, load_config, validate_config
from .reports import render_junit, render_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aev", description="Build and verify offline AI agent evidence vaults.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect", help="scan files, parse evidence, and emit reports")
    collect.add_argument("--root", default=".", help="delivery workspace root")
    collect.add_argument("--evidence", default=None, help="directory containing evidence JSON/JSONL/TXT files")
    collect.add_argument("--out", default="vault", help="output directory")
    collect.add_argument("--config", default=None, help="JSON config path")
    collect.add_argument("--format", action="append", choices=["all", "json", "markdown", "md", "junit"], default=None)
    collect.add_argument("--minimum-score", type=int, default=None, help="override config minimum_score")
    collect.add_argument("--quiet", action="store_true")

    check = subparsers.add_parser("check", help="verify file hashes from a manifest")
    check.add_argument("--manifest", required=True, help="manifest.json path")
    check.add_argument("--root", default=None, help="override root path")
    check.add_argument("--junit", default=None, help="optional JUnit output path")

    validate = subparsers.add_parser("validate-config", help="validate a JSON config")
    validate.add_argument("--config", required=True)

    score = subparsers.add_parser("score", help="print manifest score and failing checks")
    score.add_argument("--manifest", required=True)
    score.add_argument("--json", action="store_true", help="print machine-readable JSON")
    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "collect":
            formats = args.format or ["all"]
            overrides = {"minimum_score": args.minimum_score}
            result = collect_vault(args.root, args.evidence, args.out, args.config, formats, overrides)
            if not args.quiet:
                print(f"manifest: {result.output_files.get('json', Path(args.out) / 'manifest.json')}")
                print(f"score: {result.manifest.score}")
                print(f"gate: {'PASS' if result.gate_passed else 'FAIL'}")
            return result.exit_code
        if args.command == "check":
            result = verify_manifest(args.manifest, args.root)
            if args.junit:
                Path(args.junit).write_text(render_junit(result.manifest), encoding="utf-8", newline="\n")
            print(f"integrity: {'PASS' if result.gate_passed else 'FAIL'}")
            failed = [check for check in result.manifest.checks if check.status != "passed"]
            for check_result in failed[:20]:
                print(f"{check_result.id}: {check_result.message}", file=sys.stderr)
            return result.exit_code
        if args.command == "validate-config":
            config = load_config(Path(args.config))
            for key, value in explain_config(config):
                print(f"{key}: {value}")
            return 0
        if args.command == "score":
            manifest = load_manifest(args.manifest)
            failed = [check.to_dict() for check in manifest.checks if check.status != "passed"]
            if args.json:
                print(json.dumps({"score": manifest.score, "gate": not failed, "failed_checks": failed}, ensure_ascii=False))
            else:
                print(f"score: {manifest.score}")
                print(f"gate: {'PASS' if not failed else 'FAIL'}")
                for check in failed:
                    print(f"- {check['id']}: {check['message']}")
            return 0 if not failed else 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

