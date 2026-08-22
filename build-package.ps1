<#
.SYNOPSIS
    Build a KiCad PCM plugin package zip (metadata.json + plugins/ + resources/).

.DESCRIPTION
    Produces: <OutDir>/<ZipBase>-v<Version>-<Date>.zip

    - plugins/ gets all files from PluginDir EXCEPT icon-64x64.*
      (the PCM archive must not contain unrelated files; the 24x24 toolbar
      icon.png stays).
    - resources/icon.png gets the 64x64 PCM icon
      (default: <PluginDir>\icon-64x64.png).
    - metadata.json is copied as-is and must NOT contain download_* keys.

.PARAMETER PluginDir
    Source folder containing the plugin files (default: "plugins").

.PARAMETER MetadataFile
    Path to metadata.json (default: metadata.json next to the script).

.PARAMETER Icon64
    64x64 png used for resources/icon.png (default: <PluginDir>\icon-64x64.png).

.PARAMETER Version
    Version string, e.g. "1.0.2". If empty, read def_version from
    <PluginDir>\config.py.

.PARAMETER Date
    Date string YYYYMMDD. If empty, read def_date from <PluginDir>\config.py,
    else today.

.PARAMETER ZipBase
    Zip file base name (default: current folder name).

.PARAMETER OutDir
    Output folder for the zip (default: "release").

.EXAMPLE
    .\build-package.ps1 -PluginDir qihe -ZipBase ki-qihe
#>
param(
    [string]$PluginDir = "plugins",
    [string]$MetadataFile = "metadata.json",
    [string]$Icon64 = "",
    [string]$Version = "",
    [string]$Date = "",
    [string]$ZipBase = "",
    [string]$OutDir = "release"
)

$ErrorActionPreference = "Stop"

if (-not $ZipBase) { $ZipBase = Split-Path (Get-Location) -Leaf }

# Resolve version/date from config.py when not supplied
$configFile = Join-Path $PluginDir "config.py"
if ((-not $Version -or -not $Date) -and (Test-Path $configFile)) {
    $cfg = Get-Content $configFile -Raw
    if (-not $Version -and $cfg -match 'def_version\s*=\s*["'']([^"'']+)') { $Version = $Matches[1] }
    if (-not $Date -and $cfg -match 'def_date\s*=\s*["'']([^"'']+)') { $Date = ($Matches[1] -replace '-', '') }
}
if (-not $Date) { $Date = Get-Date -Format "yyyyMMdd" }
if (-not $Version) { throw "Version not supplied and not found in $configFile" }

if (-not $Icon64) { $Icon64 = Join-Path $PluginDir "icon-64x64.png" }
if (-not (Test-Path $Icon64)) { throw "64x64 icon not found: $Icon64" }
if (-not (Test-Path $MetadataFile)) { throw "metadata.json not found: $MetadataFile" }
if (-not (Test-Path $PluginDir)) { throw "Plugin source folder not found: $PluginDir" }

$zipName = "$ZipBase-v$Version-$Date.zip"
$zipPath = Join-Path $OutDir $zipName

$build = Join-Path ([System.IO.Path]::GetTempPath()) ("pcm-build-" + [guid]::NewGuid().ToString("N"))
$bPlugins = Join-Path $build "plugins"
$bResources = Join-Path $build "resources"
New-Item -ItemType Directory -Path $bPlugins, $bResources -Force | Out-Null
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

# 1. plugin code + 24x24 toolbar icon (exclude 64x64 variants)
Get-ChildItem $PluginDir -File | Where-Object { $_.Name -notlike "icon-64x64.*" } |
    ForEach-Object { Copy-Item $_.FullName -Destination $bPlugins }

# 2. PCM icon: 64x64 -> resources/icon.png
Copy-Item $Icon64 -Destination (Join-Path $bResources "icon.png")

# 3. package metadata
Copy-Item $MetadataFile -Destination $build

# 4. zip archive-root contents
if (Test-Path $zipPath) { Remove-Item $zipPath }
Compress-Archive -Path (Join-Path $build "*") -DestinationPath $zipPath
Remove-Item $build -Recurse -Force

Write-Host "Created $zipPath"
