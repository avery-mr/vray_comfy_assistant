"""Offline tests for Comfy Router payload shape."""

from __future__ import annotations

import unittest

from comfy_backend import resolution_tier, router_edit_body, router_model_id
from gemini_smoke import walk_image_b64


class RouterPayloadTests(unittest.TestCase):
    def test_edit_body_includes_png_part(self) -> None:
        body = router_edit_body("keep the building", b"fake-png")
        parts = body["contents"][0]["parts"]
        self.assertEqual(parts[0]["text"], "keep the building")
        self.assertIn("inlineData", parts[1])
        self.assertEqual(parts[1]["inlineData"]["mimeType"], "image/png")

    def test_default_router_model(self) -> None:
        self.assertEqual(
            router_model_id({}),
            "vertexai/gemini-nano-banana-2.1",
        )
        self.assertEqual(
            router_model_id({"comfy": {"routerModel": "vertexai/gemini-3-pro-image"}}),
            "vertexai/gemini-3-pro-image",
        )

    def test_resolution_tier_follows_long_side(self) -> None:
        self.assertEqual(resolution_tier(1280, 720), "1K")
        self.assertEqual(resolution_tier(1376, 768), "1K")
        self.assertEqual(resolution_tier(1920, 1080), "2K")
        self.assertEqual(resolution_tier(2560, 1440), "2K")
        self.assertEqual(resolution_tier(3840, 2160), "4K")

    def test_walk_router_inline(self) -> None:
        payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"inlineData": {"mimeType": "image/png", "data": "QUJD"}}
                        ]
                    }
                }
            ]
        }
        self.assertEqual(walk_image_b64(payload), "QUJD")


if __name__ == "__main__":
    unittest.main()
