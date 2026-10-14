# Agent notes

Read this, then `docs/decisions.md` and `docs/setup.md`, before changing the pipeline.

## What works

3ds Max 2027.2, V-Ray 7.40.04. The floater is `max_client/nano_banana_vfb.ms`. It writes `jobs/job_*/run.bat`, starts it with `HiddenDOSCommand` (no `prompt:` argument), and polls `done.txt`.

Capture leaves Display Correction on. The PNG is the picture in the VFB (8-bit, display-referred). The result is `chaos.ref.external` under `chaos.displayCorrection`, `as_foreground` false, path property `#image`, `use_image` true. Parent 0 (root) fails. There is no MaxScript reorder; the user may drag the layer. The view is applied again to an already view-baked PNG (known double-grade). Do not switch back to an ACEScg / OCIO-in-the-graph path unless asked.

## Graph

`config` `comfy.workflow` is `architectural-enhance`. That manifest selects the API JSON and the node ids:

- Load Image `10`, field `image`
- Nano Banana node `20`: `prompt`, `model.resolution`, `model.thinking_level`
- ImageScale `22` center-crops to the source width and height
- Save Image `9`

`workflows/api/wf_test_01.json` is an older color-shader test. The floater does not run it.

The floater prompt is the whole prompt (`--no-structure-prefix`, written to `prompt.txt` so quotes survive `cmd`). Resolution: long side ≤ 1400 → `1K`, ≤ 2800 → `2K`, else `4K`.

## Do not

- Put the Comfy key in `example.config.json`, the MaxScript, or any committed file. Read it from `config/local.config.json` `comfy.apiKey`, then `COMFY_API_KEY`.
- Commit `jobs/`, `samples/`, `probe/`, or client stills.
- Send EXR. PNG only.
- Build a custom VFB layer type.
- Revive the floater backend dropdown (`gemini`, `comfy-router`) unless asked.
- Parent the Image layer to Foregrounds or set `as_foreground` true.

## MaxScript traps already hit

- .NET Hashtable uses `set_Item` / `get_Item`, not `.item`.
- `HiddenDOSCommand` `prompt:` is a string. Do not pass `false`.
- Write the bat with `format "%\n"`, not `print` (print adds quotes).
- `echo %ERRORLEVEL% > file` needs a space before `>`.
- If a handler throws, `vcaBusy` stays true until the script is `fileIn`'d again.
- 3ds Max's child Python is Max's interpreter, and it overrides `PYTHONPATH` to the Max Python directory. `comfy-sdk` must be installed for that interpreter (user site is fine). Package import name is `comfy_sdk`.

## Verify

`python scripts/test_comfy_backend.py` from `scripts/` (no network). A live check is Generate in Max with dry run off, then the new `jobs/job_*/log.txt`.
