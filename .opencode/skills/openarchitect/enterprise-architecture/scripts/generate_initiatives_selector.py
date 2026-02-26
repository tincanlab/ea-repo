#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _ensure_common_python_on_path() -> None:
    common_python = Path(__file__).resolve().parents[2] / "common" / "python"
    common_python_str = str(common_python)
    if common_python_str not in sys.path:
        sys.path.insert(0, common_python_str)


_ensure_common_python_on_path()

from openarchitect_skill_common.initiative_selector import (  # noqa: E402
    build_selector_from_pipeline_path,
    load_yaml_payload,
    selector_payloads_equal,
    write_yaml_payload,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate architecture/portfolio/initiatives.yml from "
            "architecture/portfolio/initiative-pipeline.yml."
        )
    )
    parser.add_argument(
        "--pipeline",
        default="architecture/portfolio/initiative-pipeline.yml",
        help="Source initiative pipeline YAML path.",
    )
    parser.add_argument(
        "--out",
        default="architecture/portfolio/initiatives.yml",
        help="Generated selector manifest path.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check-only mode: fail when --out does not match generated content.",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Allow generation with zero publish_to_selector=true initiatives.",
    )
    args = parser.parse_args(argv)

    try:
        pipeline_path = Path(args.pipeline).resolve()
        out_path = Path(args.out).resolve()

        build = build_selector_from_pipeline_path(pipeline_path)
        if build.errors:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": "pipeline_validation_failed",
                        "details": build.errors,
                    },
                    ensure_ascii=True,
                )
            )
            return 1

        if not args.allow_empty and not build.payload.get("initiatives"):
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": "empty_selector",
                        "message": (
                            "No initiatives were selected for routing. Set routing.publish_to_selector=true "
                            "for at least one initiative, or pass --allow-empty."
                        ),
                    },
                    ensure_ascii=True,
                )
            )
            return 1

        if args.check:
            if not out_path.exists():
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error": "selector_missing",
                            "message": f"selector file not found: {out_path}",
                        },
                        ensure_ascii=True,
                    )
                )
                return 1
            existing = load_yaml_payload(out_path)
            in_sync = selector_payloads_equal(
                expected_payload=build.payload,
                actual_payload=existing,
            )
            print(
                json.dumps(
                    {
                        "ok": bool(in_sync),
                        "check_mode": True,
                        "pipeline": str(pipeline_path),
                        "out": str(out_path),
                        "selected_count": len(build.selected_ids),
                        "skipped_count": len(build.skipped_ids),
                    },
                    ensure_ascii=True,
                )
            )
            return 0 if in_sync else 1

        write_yaml_payload(out_path, build.payload)
        print(
            json.dumps(
                {
                    "ok": True,
                    "pipeline": str(pipeline_path),
                    "out": str(out_path),
                    "selected_ids": build.selected_ids,
                    "skipped_ids": build.skipped_ids,
                },
                ensure_ascii=True,
            )
        )
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
