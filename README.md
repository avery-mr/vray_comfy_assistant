# V-Ray Comfy assistant

Internal tool. From 3ds Max, snapshot the composited V-Ray frame buffer as a display-referred PNG (Display Correction left on), send that PNG plus a prompt to one Comfy Cloud workflow, and put the result back as a built-in VFB Image layer under Display Correction.

This is not a Chaos custom compositor plugin. The layer class is the built-in `chaos.ref.external`.

The only live path is `comfy-workflow` against `workflows/api/nanobana_wf_test_01.json` (Gemini Nano Banana 2.1 on cloud.comfy.org). Direct Gemini and Comfy Router code is still in `scripts/` and is not used by the floater.

## Layout

```text
AGENTS.md                 notes for the next coding agent
docs/setup.md             install, key, Max floater
docs/decisions.md         VFB constraints and color path
max_client/nano_banana_vfb.ms
scripts/run_job.py        Max and the CLI both call this
scripts/comfy_backend.py
workflows/api/nanobana_wf_test_01.json
workflows/manifests/architectural-enhance.json
config/example.config.json
```

## Quick start

Copy `config/example.config.json` to `config/local.config.json` and set `comfy.apiKey`. That file is gitignored. See [docs/setup.md](docs/setup.md).

In 3ds Max, after a VFB render:

```text
fileIn "<repo>\max_client\nano_banana_vfb.ms"
```

The floater finds the repo from its own path. Prompt and thinking level (`MINIMAL`, `MEDIUM`, `HIGH`) go to the graph. Resolution (`1K`, `2K`, or `4K`) is chosen from the snapshot’s long side.
