param(
    [string]$OrcaBin = 'C:\Program Files\OrcaSlicer\orca-slicer.exe',
    [string]$Workspace = (Join-Path $env:USERPROFILE 'OrcaMCP'),
    [switch]$Desktop
)
$ErrorActionPreference = 'Stop'
$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not (Test-Path -LiteralPath $OrcaBin -PathType Leaf)) {
    throw 'OrcaSlicer executable missing. Supply -OrcaBin with the installed path.'
}
$PythonExe = Join-Path $ProjectDir '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $PythonExe)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv (Join-Path $ProjectDir '.venv')
    } else {
        & python -m venv (Join-Path $ProjectDir '.venv')
    }
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required; venv creation failed.' }
}
$PackageSpec = $ProjectDir
if ($Desktop) { $PackageSpec += '[desktop]' }
& $PythonExe -m pip install $PackageSpec
if ($LASTEXITCODE -ne 0) { throw 'Package installation failed.' }
$ConfigArgs = @((Join-Path $PSScriptRoot 'make_config.py'), '--binary', $OrcaBin, '--root', $Workspace, '--output', (Join-Path $ProjectDir 'mcp-config.json'))
if ($Desktop) { $ConfigArgs += '--desktop' }
& $PythonExe @ConfigArgs
if ($LASTEXITCODE -ne 0) { throw 'MCP configuration generation failed.' }
Write-Host 'Installation complete. Import mcp-config.json into your local stdio MCP client.'
