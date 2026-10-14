#!/usr/bin/env python3
"""Unified job runner: gemini | comfy-router | comfy-workflow.

Max and the CLI both call this. --dry-run copies the snapshot and writes metadata
without leaving the machine.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

from comfy_backend import (
    comfy_api_key,
    generate_via_comfy_router,
    generate_via_comfy_workflow,
    router_model_id,
)
from gemini_smoke import (
    STRUCTURE_PROMPT_PREFIX,
    api_key as gemini_key,
    build_metadata,
    generate_via_rest,
    load_config,
    repo_root,
    write_metadata,
    write_placeholder_png,
)

BACKENDS = ("gemini", "comfy-router", "comfy-workflow")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=BACKENDS, default=None)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--prompt-file", type=Path, default=None)
    parser.add_argument(
        "--thinking-level",
        default="MEDIUM",
        choices=("MINIMAL", "MEDIUM", "HIGH"),
    )
    parser.add_argument("--model", default=None, help="Gemini id or Comfy Router model id")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--metadata", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write-placeholder", action="store_true")
    parser.add_argument("--no-structure-prefix", action="store_true")
    return parser.parse_args(argv)


def resolve_backend(args: argparse.Namespace, config: dict[str, Any]) -> str:
    raw = args.backend or config.get("backend") or "gemini"
    if raw not in BACKENDS:
        raise SystemExit(f"Unknown backend {raw!r}; expected {BACKENDS}")
    return raw


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = repo_root()
    if args.write_placeholder:
        dest = root / "samples" / "placeholder.png"
        write_placeholder_png(dest)
        print(f"Wrote {dest}")
        return 0

    config = load_config(args.config)
    backend = resolve_backend(args, config)
    color_space = config.get("colorSpace", "sRGB display-referred")
    source = args.input or (root / "samples" / "placeholder.png")
    if not source.exists():
        write_placeholder_png(source)
    output = args.output or (root / "output" / f"job-{int(time.time())}.png")
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = args.metadata or output.with_name(output.stem + ".metadata.json")

    if args.prompt_file:
        prompt = args.prompt_file.read_text(encoding="utf-8-sig").strip()
    else:
        prompt = args.prompt or "subtle overcast atmosphere, keep architecture"
    if not prompt:
        print("Prompt is empty.", file=sys.stderr)
        return 2
    if not args.no_structure_prefix:
        prompt = STRUCTURE_PROMPT_PREFIX + prompt

    model_label = args.model or config.get("model") or backend
    extra: dict[str, Any] = {"backend": backend}
    started = time.perf_counter()

    try:
        if args.dry_run:
            output.write_bytes(source.read_bytes())
        elif backend == "gemini":
            key = gemini_key()
            if not key:
                print("Set GEMINI_API_KEY. Use --dry-run to skip the network.", file=sys.stderr)
                return 2
            model_label = args.model or config.get("model") or "gemini-nano-banana-2.1"
            image_bytes, raw = generate_via_rest(
                source.read_bytes(),
                prompt,
                str(model_label),
                key,
                str(config.get("apiRevision") or "2026-05-20"),
            )
            output.write_bytes(image_bytes)
            extra["interactionId"] = (raw or {}).get("id") if isinstance(raw, dict) else None
        elif backend == "comfy-router":
            key = comfy_api_key(config)
            if not key:
                print(
                    "Set comfy.apiKey in config/local.config.json, or COMFY_API_KEY. "
                    "Use --dry-run to skip the network.",
                    file=sys.stderr,
                )
                return 2
            model_label = router_model_id(config, args.model)
            image_bytes, raw = generate_via_comfy_router(
                source.read_bytes(), prompt, str(model_label), key
            )
            output.write_bytes(image_bytes)
            extra["routerModel"] = model_label
            extra["comfyRequest"] = (raw or {}).get("request_id") if isinstance(raw, dict) else None
        else:
            key = comfy_api_key(config)
            if not key:
                print(
                    "Set comfy.apiKey in config/local.config.json, or COMFY_API_KEY. "
                    "Use --dry-run to skip the network.",
                    file=sys.stderr,
                )
                return 2
            image_bytes, raw = generate_via_comfy_workflow(
                source,
                prompt,
                root,
                config,
                key,
                thinking_level=args.thinking_level,
            )
            output.write_bytes(image_bytes)
            extra.update(raw)
            model_label = extra.get("workflow") or "comfy-workflow"
    except Exception as exc:  # noqa: BLE001
        write_metadata(
            metadata_path,
            build_metadata(
                source=source,
                output=output,
                prompt=prompt,
                model=str(model_label),
                color_space=str(color_space),
                dry_run=False,
                elapsed_s=time.perf_counter() - started,
                extra={**extra, "error": str(exc)},
            ),
        )
        print(str(exc), file=sys.stderr)
        return 1

    write_metadata(
        metadata_path,
        build_metadata(
            source=source,
            output=output,
            prompt=prompt,
            model=str(model_label),
            color_space=str(color_space),
            dry_run=bool(args.dry_run),
            elapsed_s=time.perf_counter() - started,
            extra=extra,
        ),
    )
    print(output)
    print(metadata_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
