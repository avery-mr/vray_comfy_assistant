# TODO

V-Ray VFB PNG → Comfy Cloud Nano Banana 2.1 → VFB Image layer under Display Correction.

Read `AGENTS.md` first.

## Done

- Floater `max_client/nano_banana_vfb.ms` captures with Display Correction on, runs only `comfy-workflow`, and creates `chaos.ref.external` under Display Correction with `as_foreground` false.
- Prompt is sent to node 20. Thinking level is a floater dropdown (`MINIMAL`, `MEDIUM`, `HIGH`). Resolution is chosen from the snapshot long side.
- Graph `workflows/api/nanobana_wf_test_01.json`: Load Image 10 → Nano Banana 20 → ImageScale 22 (center, source size) → Save Image 9.
- `comfy-sdk` is the Python package (`import comfy_sdk`). It must be installed for the Python that Max launches.
- Key is read from `config/local.config.json` `comfy.apiKey`, then `COMFY_API_KEY`.

## Next

1. On the workstation, copy `config/local.config.json` into place (or create it from `example.config.json` and set `comfy.apiKey`). Install `comfy-sdk` for that machine’s Max Python. `fileIn` the floater and Generate with dry run off.
2. Confirm the new Image layer matches the frame and that the prompt actually changed the picture.
3. Drag the layer if it needs to sit above other corrections. There is no reorder API.

## Do not

- Commit `jobs/`, `samples/`, `local.config.json`, or the API key.
- Send EXR, or put OCIO config loading back into the cloud graph, unless asked.
- Put Gemini or Comfy Router back on the floater unless asked.
- Build a custom VFB layer type.

## Known limits

- The PNG is display-referred, and the layer is still under Display Correction, so the view is applied twice.
- Blend mode stays at the Image default (26). Source RGB uses 0 (Overwrite). Inject does not set blend.
- `wf_test_01.json` is an old color-shader export. It is not the live graph.
