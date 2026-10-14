# Decisions

Snapshot the composited V-Ray VFB as a display-referred PNG, run one Comfy Cloud graph, and put the PNG back as a built-in Image layer. Not a Chaos custom compositor plugin.

Probed once on Max 2027.2 / V-Ray 7.40.04. The probe scripts and dumps are not in the repo. The constraints below are the result.

## Pipeline

```text
VFB save PNG, Display Correction left on
        |
        v
scripts/run_job.py  --backend comfy-workflow
        |
        v
cloud.comfy.org   workflows/api/nanobana_wf_test_01.json
        |
        v
VFB Image layer under Display Correction (as_foreground false)
```

The floater does not offer Gemini or Comfy Router. Those functions remain in `scripts/` and are unused by Max.

`comfy.workflow` in config names a file in `workflows/manifests/`. That manifest names the API JSON and the node ids. The live manifest is `architectural-enhance.json` → `nanobana_wf_test_01.json`.

Node 20 is `GeminiNanoBanana2V2` (Nano Banana 2.1), aspect ratio `auto`, resolution set per job to `1K` / `2K` / `4K` from the snapshot long side (≤1400, ≤2800, else 4K). Node 22 `ImageScale` with crop `center` matches the source pixel size. Save Image is node 9. Load Image is node 10.

`auto` does not emit the source dimensions. It picks a supported ratio, and the resolution tier picks a fixed pixel size (16:9 at 1K is 1376×768). The scale node is what makes the layer cover the frame.

## Color

Display Correction is a singleton on the whole stack. An Image layer cannot parent to root. It is created under Display Correction, so the view runs again on a PNG that already has the view baked in. That double-grade is accepted for now.

OCIO inside the Comfy graph is parked. The Radiance config widgets want a filesystem path on the cloud worker. Uploaded assets are not paths, and the worker cannot read the Max OCIO file. The ACES 2.0 output node runs without a file and cannot be inverted.

Capture does not toggle `#ocio`, `#srgb`, `#icc`, or `#gamma22`. It calls `vfbControl #saveimage`.

PNG only. EXR was rejected for Load Image and Cloud uploads.

The result layer is a frozen snapshot. Later Exposure changes do not update it until Generate runs again.

## VFB facts

| Item | Value |
| --- | --- |
| Image class | `chaos.ref.external` |
| Create parents that work | Display Correction, Foregrounds, Backgrounds. Root id 0 fails |
| File path | `#image` (string) and `#use_image = true` |
| Inject | parent `chaos.displayCorrection`, opacity 1, `as_foreground` false. Blend mode is left at the default (26) |
| Channels | Prefer effects result, else RGB. `preferEffectsResult` only matters when that channel exists |
| Reorder | No MaxScript API. `createLayer` only chooses the parent |

## Secrets

The shared team key goes in gitignored `config/local.config.json` as `comfy.apiKey`. `COMFY_API_KEY` is the fallback when that string is empty. Do not commit the key. Live runs send pixels to Comfy Cloud. Metadata `pixelsLeaveStudio` is true when dry-run is off.
