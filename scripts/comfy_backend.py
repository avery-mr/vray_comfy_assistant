"""Comfy Router (partner models) and Comfy Cloud/v2 workflow backends.

Router: POST https://api.comfy.org/v2/models/{provider}/{model}
  Auth: COMFY_API_KEY (X-API-Key). No subscription required; pay-per-use credits.

Workflow: comfy-sdk Comfy().workflows / assets / run
  Auth: same key. Default host https://cloud.comfy.org (paid API). Self-host:
  COMFY_BASE_URL=http://127.0.0.1:8189 (comfy-api-proxy).
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from gemini_smoke import walk_image_b64

ROUTER_BASE = "https://api.comfy.org/v2/models"


def comfy_api_key(config: dict[str, Any] | None = None) -> str:
    """Key from gitignored local config, then the process environment.

    ``config/local.config.json`` is how a shared internal key reaches 3ds Max.
    Max snapshots its environment at launch, so a variable set later is invisible
    to the Generate button. The tracked example config leaves this blank.
    """
    if isinstance(config, dict):
        comfy = config.get("comfy") if isinstance(config.get("comfy"), dict) else {}
        file_key = str(comfy.get("apiKey") or "").strip()
        if file_key:
            return file_key
    return os.environ.get("COMFY_API_KEY") or os.environ.get("COMFY_CLOUD_API_KEY") or ""


def router_model_id(config: dict[str, Any], override: str | None = None) -> str:
    if override:
        return override
    comfy = config.get("comfy") if isinstance(config.get("comfy"), dict) else {}
    return str(
        comfy.get("routerModel")
        or "vertexai/gemini-nano-banana-2.1"
    )


def router_edit_body(prompt: str, png_bytes: bytes) -> dict[str, Any]:
    return {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": "image/png",
                            "data": base64.b64encode(png_bytes).decode("ascii"),
                        }
                    },
                ],
            }
        ],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }


def _http_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    key: str,
    timeout: int = 180,
) -> tuple[int, dict[str, Any] | None, str]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"X-API-Key": key, "Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
        headers["Idempotency-Key"] = str(uuid.uuid4())
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw) if raw.strip() else {}
            return response.status, parsed, raw
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail) if detail else {}
        except json.JSONDecodeError:
            parsed = {"error": detail}
        return exc.code, parsed, detail


def generate_via_comfy_router(
    png_bytes: bytes,
    prompt: str,
    model_id: str,
    key: str,
) -> tuple[bytes, dict[str, Any]]:
    body = router_edit_body(prompt, png_bytes)
    status, parsed, raw = _http_json(
        f"{ROUTER_BASE}/{model_id}",
        method="POST",
        payload=body,
        key=key,
    )
    if status in (200, 201) and parsed:
        b64 = walk_image_b64(parsed)
        if b64:
            return base64.b64decode(b64), parsed
        request_id = parsed.get("request_id") or parsed.get("id")
        if request_id:
            return _poll_router_result(model_id, str(request_id), key)
    if status == 201:
        request_id = (parsed or {}).get("request_id") or (parsed or {}).get("id")
        if request_id:
            return _poll_router_result(model_id, str(request_id), key)
    raise RuntimeError(f"Comfy Router HTTP {status}: {raw[:2000]}")


def _poll_router_result(
    model_id: str, request_id: str, key: str, timeout_s: float = 180.0
) -> tuple[bytes, dict[str, Any]]:
    deadline = time.time() + timeout_s
    status_url = f"{ROUTER_BASE}/{model_id}/requests/{request_id}/status"
    result_url = f"{ROUTER_BASE}/{model_id}/requests/{request_id}"
    while time.time() < deadline:
        code, parsed, raw = _http_json(status_url, key=key, timeout=60)
        state = ""
        if isinstance(parsed, dict):
            state = str(parsed.get("status") or parsed.get("state") or "").upper()
        if state in {"COMPLETED", "SUCCEEDED", "SUCCESS"}:
            rcode, result, rraw = _http_json(result_url, key=key, timeout=60)
            if rcode == 202:
                time.sleep(2)
                continue
            if not isinstance(result, dict):
                raise RuntimeError(f"Comfy Router empty result: {rraw[:1000]}")
            b64 = walk_image_b64(result)
            if not b64:
                raise RuntimeError("Comfy Router completed but returned no image.")
            return base64.b64decode(b64), result
        if state in {"FAILED", "CANCELLED", "CANCELED", "ERROR"}:
            raise RuntimeError(f"Comfy Router job {state}: {raw[:2000]}")
        time.sleep(2)
    raise RuntimeError(f"Comfy Router timed out waiting for {request_id}")


def png_size(path: Path) -> tuple[int, int]:
    """Width and height from a PNG IHDR. The VFB snapshot is always a PNG."""
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"Expected a PNG: {path}")
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    return width, height


def resolution_tier(width: int, height: int) -> str:
    """Pick Nano Banana 1K / 2K / 4K so the preset is at least the snapshot.

    16:9 buckets are 1376, 2752, and 5504 on the long side. Thresholds sit just
    above the 1K and 2K buckets so a 1920-wide frame uses 2K and ImageScale
    downscales instead of enlarging a smaller generation.
    """
    longest = max(int(width), int(height))
    if longest <= 1400:
        return "1K"
    if longest <= 2800:
        return "2K"
    return "4K"


def load_manifest(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    comfy = config.get("comfy") if isinstance(config.get("comfy"), dict) else {}
    name = str(comfy.get("workflow") or "architectural-enhance")
    path = root / "workflows" / "manifests" / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing workflow manifest: {path}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def generate_via_comfy_workflow(
    source: Path,
    prompt: str,
    root: Path,
    config: dict[str, Any],
    key: str,
    thinking_level: str = "MEDIUM",
) -> tuple[bytes, dict[str, Any]]:
    try:
        from comfy_sdk import Comfy
        from comfy_sdk.exceptions import JobFailed
    except ImportError as exc:
        raise RuntimeError(
            "comfy-workflow backend needs: pip install comfy-sdk"
        ) from exc

    manifest = load_manifest(root, config)
    wf_rel = manifest.get("workflowFile")
    wf_path = root / "workflows" / "api" / str(wf_rel)
    if not wf_path.exists():
        raise FileNotFoundError(
            f"Export an API-format workflow to {wf_path} "
            "(Comfy: File → Export Workflow (API))."
        )

    comfy_cfg = config.get("comfy") if isinstance(config.get("comfy"), dict) else {}
    base = comfy_cfg.get("baseUrl") or os.environ.get("COMFY_BASE_URL")
    if base:
        os.environ["COMFY_BASE_URL"] = str(base)

    client = Comfy(api_key=key or None)
    wf = client.workflows.from_file(str(wf_path))
    asset = client.assets.from_file(str(source))
    wf.set_input(str(manifest["imageNode"]), str(manifest.get("imageField") or "image"), asset)
    prompt_node = manifest.get("promptNode")
    if prompt_node:
        wf.set_input(str(prompt_node), str(manifest.get("promptField") or "prompt"), prompt)

    width, height = png_size(source)
    tier = resolution_tier(width, height)
    resolution_node = manifest.get("resolutionNode") or prompt_node
    if resolution_node:
        wf.set_input(
            str(resolution_node),
            str(manifest.get("resolutionField") or "model.resolution"),
            tier,
        )
    level = (thinking_level or "MEDIUM").upper()
    thinking_node = manifest.get("thinkingNode") or prompt_node
    if thinking_node:
        wf.set_input(
            str(thinking_node),
            str(manifest.get("thinkingField") or "model.thinking_level"),
            level,
        )

    try:
        job = client.run(wf, api_key=key or None)
    except JobFailed as exc:
        detail = exc.error
        extra = ""
        if detail is not None:
            extra = f" node {detail.node_id} ({detail.class_type}): {detail.message}"
        raise RuntimeError(f"{exc}{extra}") from exc
    outputs = list(job.get_outputs(str(manifest["outputNode"])))
    if not outputs:
        outputs = list(getattr(job, "outputs", []) or [])
    if not outputs:
        raise RuntimeError("Comfy workflow finished with no outputs.")
    dest = source.with_name(source.stem + "_comfy_tmp.png")
    outputs[0].to_file(str(dest))
    data = dest.read_bytes()
    dest.unlink(missing_ok=True)
    extra = {
        "jobId": getattr(job, "id", None),
        "workflow": manifest.get("id"),
        "sourceWidth": width,
        "sourceHeight": height,
        "resolution": tier,
        "thinkingLevel": level,
    }
    return data, extra
