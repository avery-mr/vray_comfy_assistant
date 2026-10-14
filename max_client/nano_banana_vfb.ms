-- Snapshot the composited V-Ray VFB look, call scripts/run_job.py, inject an Image layer.
-- fileIn this file from wherever the repo was copied. The repo root is the parent of max_client.

global vcaRepoRoot = pathConfig.removePathLeaf (pathConfig.removePathLeaf (getThisScriptFilename()))
global vcaConfig = undefined
global vcaBusy = false
global vcaPoller = undefined

fn vcaJoin a b =
(
    local left = trimRight (a as string) "\\/"
    left + "\\" + (b as string)
)

fn vcaCfgSet key val =
(
    vcaConfig.set_Item key val
    val
)

fn vcaCfgGet key =
(
    vcaConfig.get_Item key
)

fn vcaLoadConfig =
(
    local localPath = vcaJoin vcaRepoRoot @"config\local.config.json"
    local examplePath = vcaJoin vcaRepoRoot @"config\example.config.json"
    local path = examplePath
    if doesFileExist localPath then path = localPath
    vcaConfig = dotNetObject "System.Collections.Hashtable"
    -- Minimal parse: read known keys from a tiny Max-side reader via Python if needed.
    -- For the spike we keep defaults and override pythonExe / model from file lines.
    vcaConfig.add "pythonExe" "python"
    vcaConfig.add "model" "gemini-nano-banana-2.1"
    vcaConfig.add "backend" "comfy-workflow"
    vcaConfig.add "imageLayerClass" "chaos.ref.external"
    vcaConfig.add "imageLayerParentClass" "chaos.displayCorrection"
    vcaConfig.add "layerName" "Nano Banana"
    vcaConfig.add "preferEffectsResult" true
    if doesFileExist path then
    (
        local fs = openFile path mode:"rt"
        if fs != undefined then
        (
            while not eof fs do
            (
                local line = readLine fs
                if line == undefined then exit
                if (findString line "\"pythonExe\"") != undefined then
                (
                    local q = filterString line "\""
                    if q.count >= 4 then vcaCfgSet "pythonExe" q[4]
                )
                if (findString line "\"model\"") != undefined and (findString line "fastModel") == undefined then
                (
                    local q = filterString line "\""
                    if q.count >= 4 then vcaCfgSet "model" q[4]
                )
                if (findString line "\"imageLayerClass\"") != undefined then
                (
                    local q = filterString line "\""
                    if q.count >= 4 then vcaCfgSet "imageLayerClass" q[4]
                )
                if (findString line "\"imageLayerParentClass\"") != undefined then
                (
                    local q = filterString line "\""
                    if q.count >= 4 then vcaCfgSet "imageLayerParentClass" q[4]
                )
                if (findString line "\"layerName\"") != undefined then
                (
                    local q = filterString line "\""
                    if q.count >= 4 then vcaCfgSet "layerName" q[4]
                )
                if (findString line "\"backend\"") != undefined then
                (
                    local q = filterString line "\""
                    if q.count >= 4 then vcaCfgSet "backend" q[4]
                )
            )
            close fs
        )
    )
    vcaConfig
)

fn vcaUnwrap v =
(
    if classOf v == Array and v.count == 1 then v[1] else v
)

fn vcaFindChannelIndex names token =
(
    if names == undefined then return -1
    names = vcaUnwrap names
    if classOf names != Array then names = #(names)
    local needle = toLower token
    for i = 1 to names.count do
    (
        local n = toLower (names[i] as string)
        if (findString n needle) != undefined then return (i - 1)
    )
    -1
)

fn vcaSelectCompositedChannel =
(
    local names = undefined
    try (names = vcaUnwrap (vfbControl #getchannelnames)) catch (return false)
    local idx = vcaFindChannelIndex names "effectsresult"
    if idx < 0 then idx = vcaFindChannelIndex names "effects result"
    if idx < 0 then idx = vcaFindChannelIndex names "rgb color"
    if idx < 0 then idx = vcaFindChannelIndex names "rgb"
    if idx >= 0 then
    (
        try (vfbControl #setchannel idx) catch ()
        true
    )
    else false
)

fn vcaLayerIdByClass vfbLayers className =
(
    local ids = vfbLayers.getAllLayerIDs()
    for id in ids do
    (
        local lyr = undefined
        try (lyr = vfbLayers.getLayer id) catch ()
        if lyr != undefined then
        (
            local c = ""
            try (c = lyr.class as string) catch ()
            if c == className then return id
        )
    )
    undefined
)

fn vcaImageParentId vfbLayers =
(
    -- Probe (Max 2027 / V-Ray 7.40): chaos.ref.external cannot parent to root (id 0).
    -- Parent is Display Correction, so the Image is a sibling of Source / Lens / Foregrounds.
    local parentClass = "chaos.displayCorrection"
    try (parentClass = (vcaCfgGet "imageLayerParentClass") as string) catch ()
    local parentId = vcaLayerIdByClass vfbLayers parentClass
    if parentId != undefined then return parentId
    local dc = vcaLayerIdByClass vfbLayers "chaos.displayCorrection"
    if dc != undefined then return dc
    1
)

fn vcaSnapshotPng destPath =
(
    vcaSelectCompositedChannel()
    -- Display Correction stays on. The PNG is the picture currently in the VFB.
    vfbControl #saveimage destPath
    doesFileExist destPath
)

fn vcaSetLayerPath lyr filePath =
(
    try (lyr.use_image = true) catch ()
    local tried = #("image", "filename", "file", "filepath", "file_path", "bitmap")
    for p in tried do
    (
        try
        (
            setProperty lyr (p as name) filePath
            return true
        )
        catch ()
    )
    local names = #()
    try (names = lyr.propertyNames) catch ()
    for p in names do
    (
        local s = toLower (p as string)
        if (findString s "image") != undefined or (findString s "file") != undefined or (findString s "path") != undefined then
        (
            try
            (
                setProperty lyr (p as name) filePath
                return true
            )
            catch ()
        )
    )
    false
)

fn vcaWriteUtf8 path text =
(
    local utf8 = dotNetObject "System.Text.UTF8Encoding" false
    local writer = dotNetObject "System.IO.StreamWriter" path false utf8
    writer.Write (text as string)
    writer.Close()
    true
)

fn vcaSetLayerName lyr n =
(
    try (lyr.name = n; return true) catch ()
    try (lyr.userName = n; return true) catch ()
    false
)

fn vcaCreateResultLayer filePath =
(
    local vfbLayers = (vfbControl #getLayerMgr)[1]
    local className = (vcaCfgGet "imageLayerClass") as string
    local parentId = vcaImageParentId vfbLayers
    local lyr = undefined
    local classes = #(className, "chaos.ref.external")
    for c in classes while lyr == undefined do
    (
        try (lyr = vfbLayers.createLayer parentId c) catch ()
    )
    if lyr == undefined then return undefined
    vcaSetLayerName lyr ((vcaCfgGet "layerName") as string)
    if not (vcaSetLayerPath lyr filePath) then
        format "Could not set image path on VFB layer. Set it manually: %\n" filePath
    try (lyr.opacity = 1.0) catch ()
    try (lyr.enabled = 1) catch ()
    try (lyr.as_foreground = false) catch ()
    lyr
)

try (destroyDialog vcaNanoBananaRollout) catch ()

rollout vcaNanoBananaRollout "VFB Nano Banana Pro"
(
    edittext edtPrompt "Prompt" text:"Photorealistic architectural render of a modern building.  Realistic materials, dynamic cinematic lighting.  Add landscaping and foliage.  Fill in the background and horizon." height:80 width:360
    dropdownlist ddlThinking "Thinking" items:#("MINIMAL", "MEDIUM", "HIGH") selection:2 width:220
    checkbox chkDry "Dry run (copy snapshot, no network)" checked:false
    button btnGo "Generate into VFB layer" width:220
    label lblStatus "Idle" align:#left

    timer tmrPoll interval:1000 active:false
    local jobDir = ""
    local outputPath = ""
    local inputPath = ""

    on btnGo pressed do
    (
        if vcaBusy then
        (
            lblStatus.text = "Already running"
            return false
        )
        if vfbControl == undefined then
        (
            lblStatus.text = "V-Ray VFB not available"
            return false
        )
        local prompt = trimRight (trimLeft (edtPrompt.text as string))
        if prompt.count == 0 then
        (
            lblStatus.text = "Enter a prompt"
            return false
        )
        vcaLoadConfig()
        local jobs = vcaJoin vcaRepoRoot "jobs"
        makeDir jobs
        inputPath = vcaJoin jobs ("vfb_capture_" + (timeStamp() as string) + ".png")
        outputPath = vcaJoin jobs ("vfb_result_" + (timeStamp() as string) + ".png")
        lblStatus.text = "Capturing VFB..."
        if not (vcaSnapshotPng inputPath) then
        (
            lblStatus.text = "Capture failed. Render first, then save PNG from VFB."
            return false
        )
        vcaBusy = true
        local extra = ""
        if chkDry.checked then extra = " --dry-run"
        local thinking = ddlThinking.selected as string
        local py = vcaJoin vcaRepoRoot @"scripts\run_job.py"
        local exe = (vcaCfgGet "pythonExe") as string
        local cfg = vcaJoin vcaRepoRoot @"config\example.config.json"
        if doesFileExist (vcaJoin vcaRepoRoot @"config\local.config.json") then
            cfg = vcaJoin vcaRepoRoot @"config\local.config.json"
        jobDir = vcaJoin jobs ("job_" + (timeStamp() as string))
        makeDir jobDir
        local promptFile = vcaJoin jobDir "prompt.txt"
        vcaWriteUtf8 promptFile prompt
        local bat = vcaJoin jobDir "run.bat"
        local doneFile = vcaJoin jobDir "done.txt"
        local logFile = vcaJoin jobDir "log.txt"
        local bf = createFile bat
        local line1 = "@echo off"
        local line2 = "\"" + exe + "\" \"" + py + "\" --config \"" + cfg + "\" --backend \"comfy-workflow\" --input \"" + inputPath + "\" --output \"" + outputPath + "\" --prompt-file \"" + promptFile + "\" --thinking-level " + thinking + " --no-structure-prefix" + extra + " 1> \"" + logFile + "\" 2>&1"
        local line3 = "echo %ERRORLEVEL% > \"" + doneFile + "\""
        format "%\n" line1 to:bf
        format "%\n" line2 to:bf
        format "%\n" line3 to:bf
        close bf
        lblStatus.text = "Running Nano Banana..."
        HiddenDOSCommand ("\"" + bat + "\"") startpath:jobDir donotwait:true
        tmrPoll.active = true
        true
    )

    on tmrPoll tick do
    (
        local doneFile = vcaJoin jobDir "done.txt"
        if jobDir != "" and doesFileExist doneFile then
        (
            tmrPoll.active = false
            vcaBusy = false
            local code = "1"
            local df = openFile doneFile mode:"rt"
            if df != undefined then
            (
                code = trimRight (readLine df)
                close df
            )
            if code == "0" and doesFileExist outputPath then
            (
                local lyr = vcaCreateResultLayer outputPath
                if lyr == undefined then
                    lblStatus.text = "Job OK. Could not create VFB layer. Open: " + outputPath
                else
                    lblStatus.text = "Layer created. Toggle / opacity in VFB. " + outputPath
            )
            else
            (
                lblStatus.text = "Job failed (exit " + code + "). See jobs folder log."
            )
        )
    )
)

vcaLoadConfig()
createDialog vcaNanoBananaRollout 400 250
