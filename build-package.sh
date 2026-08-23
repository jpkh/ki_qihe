#!/bin/sh
##########################################################
#
# Script: build-package.sh
# Author: Jani Hirvinen aka jpkh
# Contact: [Use GitHub issues for questions and suggestions]
#
# Date: 2024-04-07 (updated 2026-08-23)
# Version: 1.1.0
#
# Description: Build the KiCad PCM package zip for the QIHE plugin.
#              Mirror of build-package.ps1 - both produce the same
#              ISO 21320-1 zip with forward-slash entry names.
#
# Works:
#  - Linux
#  - MacOS
#  - Git Bash / Cygwin on Windows
#
##########################################################

set -e

plugin_dir="qihe"
metadata_file="metadata.json"
icon64="resources/icon.png"
zip_base="ki-qihe"
out_dir="release"

repo_root=$(pwd)

# Extract version and date from config.py
config_file="${plugin_dir}/config.py"
def_version=$(grep 'def_version' "$config_file" | cut -d "=" -f 2 | tr -d " \r'\"")
def_date=$(grep 'def_date' "$config_file" | cut -d "=" -f 2 | tr -d " \r'\"-")

echo "Version: ${def_version}"
echo "Date: ${def_date}"

# Staging folder (cleaned up on exit)
build_dir=$(mktemp -d)
trap 'rm -rf "$build_dir"' EXIT

mkdir -p "$build_dir/plugins" "$build_dir/resources" "$out_dir"

# 1. plugin code: only .py files + the 24x24 toolbar icon.png
cp "$plugin_dir"/*.py "$build_dir/plugins/"
cp "$plugin_dir"/icon.png "$build_dir/plugins/"

# 2. PCM icon: 64x64 -> resources/icon.png
cp "$icon64" "$build_dir/resources/icon.png"

# 3. package metadata
cp "$metadata_file" "$build_dir/"

# 4. zip the archive-root contents
zip_path="${repo_root}/${out_dir}/${zip_base}-v${def_version}-${def_date}.zip"
rm -f "$zip_path"
( cd "$build_dir" && zip -r "$zip_path" . )

echo "Created ${zip_path}"

