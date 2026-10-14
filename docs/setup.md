# Setup

Tested with 3ds Max 2027.2 and V-Ray 7.40.04. The floater always runs `comfy-workflow`.

## API key

Copy `config/example.config.json` to `config/local.config.json` and set `comfy.apiKey` to the shared Comfy Cloud key. The floater passes that file to `scripts/run_job.py`. `local.config.json` is gitignored. Share it with teammates as a file, not by committing it.

`COMFY_API_KEY` still works when the config value is empty. 3ds Max only sees environment variables that existed when Max started, so the config file is the one that works from the floater.

Do not put the key in `example.config.json`.

## Python

Max launches `"python"` (`pythonExe` in the config). That must be an interpreter that can import `comfy_sdk`. On a machine where Max ships Python 3.13 and Program Files is not writable:

```text
"<3ds Max>\Python\python.exe" -m ensurepip
"<3ds Max>\Python\python.exe" -m pip install --user "comfy-sdk>=0.5"
```

Check with `PYTHONPATH` pointed at the Max Python directory, because Max overrides `PYTHONPATH` for the child process:

```text
python -c "import comfy_sdk"
```

Offline test, from `scripts/`:

```text
python test_comfy_backend.py
```

CLI dry run (no network):

```text
python scripts/run_job.py --dry-run --backend comfy-workflow --input some.png --output output/dry.png --prompt "overcast sky" --no-structure-prefix
```

## 3ds Max

Render into the V-Ray VFB first, then:

```text
fileIn "<repo>\max_client\nano_banana_vfb.ms"
```

The script sets its repo root from its own path. Reload with `fileIn` after every edit. Dry run copies the snapshot onto a new Image layer and does not call Cloud. Generate sends the prompt and the thinking level. Resolution is chosen from the snapshot.

The result layer is under Display Correction. There is no script call to move it above other layers; drag it if the stack order matters.
