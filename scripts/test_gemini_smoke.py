"""Offline tests for payload helpers — no Gemini call."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gemini_smoke import (
    build_metadata,
    walk_image_b64,
    write_placeholder_png,
)


class WalkImageTests(unittest.TestCase):
    def test_interactions_output_image(self) -> None:
        payload = {"output_image": {"mime_type": "image/png", "data": "QUJD"}}
        self.assertEqual(walk_image_b64(payload), "QUJD")

    def test_nested_inline_data(self) -> None:
        payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"inlineData": {"mimeType": "image/png", "data": "WFla"}}
                        ]
                    }
                }
            ]
        }
        self.assertEqual(walk_image_b64(payload), "WFla")


class PlaceholderAndMetadataTests(unittest.TestCase):
    def test_placeholder_is_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.png"
            write_placeholder_png(path)
            self.assertTrue(path.read_bytes().startswith(b"\x89PNG"))

    def test_metadata_flags_pixels_leave_studio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "in.png"
            write_placeholder_png(src)
            out = Path(tmp) / "out.png"
            meta = build_metadata(
                source=src,
                output=out,
                prompt="test",
                model="gemini-3-pro-image",
                color_space="sRGB display-referred",
                dry_run=False,
                elapsed_s=1.0,
            )
            self.assertTrue(meta["pixelsLeaveStudio"])
            json.dumps(meta)


if __name__ == "__main__":
    unittest.main()
