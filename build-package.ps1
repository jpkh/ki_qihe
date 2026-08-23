<#
.SYNOPSIS
    Build a KiCad PCM plugin package zip (metadata.json + plugins/ + resources/).

.DESCRIPTION
    Produces: <OutDir>/<ZipBase>-v<Version>-<Date>.zip

    - plugins/ gets the plugin's .py files plus the 24x24 toolbar icon.png.
      Nothing else (no __pycache__, logs, or runtime data files).
    - resources/icon.png gets the 64x64 PCM icon
      (default: resources/icon.png in the repo root).
    - metadata.json is copied as-is and must NOT contain download_* keys.
    - Zip entries use forward slashes (ISO 21320-1) so the package installs
      on Windows, Linux, and macOS.

.PARAMETER PluginDir
    Source folder containing the plugin code (default: "qihe").

.PARAMETER MetadataFile
    Path to metadata.json (default: metadata.json next to the script).

.PARAMETER Icon64
    64x64 png used for resources/icon.png (default: "resources/icon.png").

.PARAMETER Version
    Version string, e.g. "1.1.0". If empty, read def_version from
    <PluginDir>\config.py.

.PARAMETER Date
    Date string YYYYMMDD. If empty, read def_date from <PluginDir>\config.py,
    else today.

.PARAMETER ZipBase
    Zip file base name (default: "ki-qihe").

.PARAMETER OutDir
    Output folder for the zip (default: "release").

.EXAMPLE
    .\build-package.ps1
#>
param(
    [string]$PluginDir = "qihe",
    [string]$MetadataFile = "metadata.json",
    [string]$Icon64 = "resources/icon.png",
    [string]$Version = "",
    [string]$Date = "",
    [string]$ZipBase = "ki-qihe",
    [string]$OutDir = "release"
)

$ErrorActionPreference = "Stop"

# Resolve paths relative to this script so the working directory doesn't matter
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not [System.IO.Path]::IsPathRooted($PluginDir)) { $PluginDir = Join-Path $ScriptRoot $PluginDir }
if (-not [System.IO.Path]::IsPathRooted($MetadataFile)) { $MetadataFile = Join-Path $ScriptRoot $MetadataFile }
if (-not [System.IO.Path]::IsPathRooted($Icon64)) { $Icon64 = Join-Path $ScriptRoot $Icon64 }
if (-not [System.IO.Path]::IsPathRooted($OutDir)) { $OutDir = Join-Path $ScriptRoot $OutDir }

# Resolve version/date from config.py when not supplied
$configFile = Join-Path $PluginDir "config.py"
if ((-not $Version -or -not $Date) -and (Test-Path $configFile)) {
    $cfg = Get-Content $configFile -Raw
    if (-not $Version -and $cfg -match 'def_version\s*=\s*["'']([^"'']+)') { $Version = $Matches[1] }
    if (-not $Date -and $cfg -match 'def_date\s*=\s*["'']([^"'']+)') { $Date = ($Matches[1] -replace '-', '') }
}
if (-not $Date) { $Date = Get-Date -Format "yyyyMMdd" }
if (-not $Version) { throw "Version not supplied and not found in $configFile" }

if (-not (Test-Path $Icon64)) { throw "64x64 icon not found: $Icon64" }
if (-not (Test-Path $MetadataFile)) { throw "metadata.json not found: $MetadataFile" }
if (-not (Test-Path $PluginDir)) { throw "Plugin source folder not found: $PluginDir" }

$zipName = "$ZipBase-v$Version-$Date.zip"
$zipPath = Join-Path $OutDir $zipName

# 1. staging folder
$build = Join-Path ([System.IO.Path]::GetTempPath()) ("pcm-build-" + [guid]::NewGuid().ToString("N"))
$bPlugins = Join-Path $build "plugins"
$bResources = Join-Path $build "resources"
New-Item -ItemType Directory -Path $bPlugins, $bResources -Force | Out-Null
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

# 2. plugin code: only .py files + the 24x24 toolbar icon.png
Get-ChildItem $PluginDir -File | Where-Object {
    $_.Extension -eq '.py' -or $_.Name -eq 'icon.png'
} | ForEach-Object { Copy-Item $_.FullName -Destination $bPlugins }

# 3. PCM icon: 64x64 -> resources/icon.png
Copy-Item $Icon64 -Destination (Join-Path $bResources "icon.png")

# 4. package metadata
Copy-Item $MetadataFile -Destination $build

# 5. zip with forward-slash entry names (ISO 21320-1)
if (Test-Path $zipPath) { Remove-Item $zipPath }
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    Get-ChildItem $build -Recurse -File | ForEach-Object {
        $entryName = $_.FullName.Substring($build.Length + 1).Replace('\', '/')
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $_.FullName, $entryName) | Out-Null
    }
}
finally {
    $zip.Dispose()
}
Remove-Item $build -Recurse -Force

Write-Host "Created $zipPath"
