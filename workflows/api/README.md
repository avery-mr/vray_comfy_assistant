# API workflows

Comfy **API-format** JSON (`File → Export Workflow (API)`).

The floater runs `nanobana_wf_test_01.json`. Node ids and the file name live in `workflows/manifests/architectural-enhance.json`.

`wf_test_01.json` is an older GLSL color-shader graph (Load Image 10 → Save Image 9). It is kept as a reference and is not selected.

Do not commit graphs that embed machine paths or client stills. When the Nano Banana graph changes, export again and update `workflowFile`, `imageNode`, `imageField`, `promptNode`, `promptField`, `resolutionNode`, `resolutionField`, `thinkingNode`, `thinkingField`, and `outputNode` in the manifest.
