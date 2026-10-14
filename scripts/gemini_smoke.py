#!/usr/bin/env python3
"""Standalone Nano Banana Pro (gemini-3-pro-image) image-to-image smoke test.

Sends a display-referred PNG + prompt to Gemini and writes the result plus metadata.json.
API key: GEMINI_API_KEY or GOOGLE_API_KEY. Never commit keys.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import struct
import sys
import time
import urllib.error
import urllib.request
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "gemini-nano-banana-2.1"
INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
API_REVISION = "2026-05-20"
STRUCTURE_PROMPT_PREFIX = (
    "Keep the camera, building geometry, and materials. "
    "Apply only the requested change. "
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        candidate = repo_root() / "config" / "local.config.json"
        if not candidate.exists():
            candidate = repo_root() / "config" / "example.config.json"
        path = candidate
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def api_key() -> str:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def png_chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc32(tag + data))


def write_placeholder_png(path: Path, width: int = 64, height: int = 48) -> None:
    """Non-confidential sRGB test chart (magenta/gray) for dry-run and API smoke."""
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            if (x // 8 + y // 8) % 2 == 0:
                rows.extend((200, 40, 160))
            else:
                rows.extend((48, 48, 48))
    compressed = zlib.compress(bytes(rows), 9)
    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += png_chunk(b"sRGB", b"\x00")
    png += png_chunk(b"IDAT", compressed)
    png += png_chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def walk_image_b64(node: Any) -> str | None:
    """Find the first inline image payload in an Interactions / generateContent JSON tree."""
    if isinstance(node, dict):
        mime = str(node.get("mime_type") or node.get("mimeType") or "")
        data = node.get("data")
        if isinstance(data, str) and data and (
            mime.startswith("image/") or node.get("type") == "image"
        ):
            return data
        inline = node.get("inlineData") or node.get("inline_data")
        if isinstance(inline, dict):
            found = walk_image_b64(inline)
            if found:
                return found
        for key in ("output_image", "outputImage", "image"):
            if key in node:
                found = walk_image_b64(node[key])
                if found:
                    return found
        for value in node.values():
            found = walk_image_b64(value)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = walk_image_b64(item)
            if found:
                return found
    return None


def post_json(url: str, payload: dict[str, Any], key: str, api_revision: str) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": key,
            "Api-Revision": api_revision,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from Gemini: {detail}") from exc


def generate_via_rest(
    image_bytes: bytes,
    prompt: str,
    model: str,
    key: str,
    api_revision: str,
) -> tuple[bytes, dict[str, Any]]:
    payload = {
        "model": model,
        "input": [
            {"type": "text", "text": prompt},
            {
                "type": "image",
                "data": base64.b64encode(image_bytes).decode("ascii"),
                "mime_type": "image/png",
            },
        ],
    }
    result = post_json(INTERACTIONS_URL, payload, key, api_revision)
    b64 = walk_image_b64(result)
    if not b64:
        raise RuntimeError("Gemini response did not contain an image payload.")
    return base64.b64decode(b64), result


def write_metadata(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def build_metadata(
    *,
    source: Path,
    output: Path,
    prompt: str,
    model: str,
    color_space: str,
    dry_run: bool,
    elapsed_s: float,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = {
        "sourcePath": str(source),
        "sourceSha256": sha256_file(source) if source.exists() else None,
        "outputPath": str(output),
        "prompt": prompt,
        "model": model,
        "colorSpace": color_space,
        "dryRun": dry_run,
        "elapsedSeconds": round(elapsed_s, 3),
        "timestampUtc": datetime.now(timezone.utc).isoformat(),
        "pixelsLeaveStudio": not dry_run,
    }
    if extra:
        meta.update(extra)
    return meta


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Source PNG (display-referred)")
    parser.add_argument("--output", type=Path, help="Output PNG path")
    parser.add_argument("--prompt", default="subtle overcast atmosphere, keep architecture")
    parser.add_argument("--model", default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--metadata", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Copy input to output; no network")
    parser.add_argument(
        "--write-placeholder",
        action="store_true",
        help="Write samples/placeholder.png and exit",
    )
    parser.add_argument(
        "--no-structure-prefix",
        action="store_true",
        help="Do not prepend the keep-geometry instruction",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = repo_root()
    if args.write_placeholder:
        dest = root / "samples" / "placeholder.png"
        write_placeholder_png(dest)
        print(f"Wrote {dest}")
        return 0

    config = load_config(args.config)
    model = args.model or config.get("model") or DEFAULT_MODEL
    color_space = config.get("colorSpace", "sRGB display-referred")
    source = args.input or (root / "samples" / "placeholder.png")
    if not source.exists():
        write_placeholder_png(source)
    output = args.output or (root / "output" / f"nano-banana-{int(time.time())}.png")
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = args.metadata or output.with_name(output.stem + ".metadata.json")

    prompt = args.prompt
    if not args.no_structure_prefix:
        prompt = STRUCTURE_PROMPT_PREFIX + prompt

    started = time.perf_counter()
    if args.dry_run:
        output.write_bytes(source.read_bytes())
        raw_response: dict[str, Any] | None = None
    else:
        key = api_key()
        if not key:
            print(
                "Set GEMINI_API_KEY (or GOOGLE_API_KEY). Use --dry-run to skip the network.",
                file=sys.stderr,
            )
            return 2
        raw_response_holder: dict[str, Any] = {}
        try:
            image_bytes, raw_response_holder = generate_via_rest(
                source.read_bytes(),
                prompt,
                model,
                key,
                str(config.get("apiRevision") or API_REVISION),
            )
            output.write_bytes(image_bytes)
            raw_response = raw_response_holder
        except Exception as exc:  # noqa: BLE001 — CLI surface
            meta = build_metadata(
                source=source,
                output=output,
                prompt=prompt,
                model=model,
                color_space=color_space,
                dry_run=False,
                elapsed_s=time.perf_counter() - started,
                extra={"error": str(exc)},
            )
            write_metadata(metadata_path, meta)
            print(str(exc), file=sys.stderr)
            return 1

    elapsed = time.perf_counter() - started
    extra = {"interactionId": None}
    if raw_response and isinstance(raw_response, dict):
        extra["interactionId"] = raw_response.get("id") or raw_response.get("name")
    meta = build_metadata(
        source=source,
        output=output,
        prompt=prompt,
        model=model,
        color_space=color_space,
        dry_run=bool(args.dry_run),
        elapsed_s=elapsed,
        extra=extra,
    )
    write_metadata(metadata_path, meta)
    print(output)
    print(metadata_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
