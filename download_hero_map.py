#!/usr/bin/env python3
"""
Downloads all 12 HERO_MAP ROS 2 bags from SharePoint with resume capability and progress tracking.
"""

import os
import sys
import json
import subprocess
from pathlib import Path

COOKIE_FILE = "/tmp/sp_cookies.txt"
BASE_URL = "https://vistec-my.sharepoint.com/personal/runj_pro_vistec_ac_th"
OUTPUT_DIR = Path("/ist-nas/users/pratchp/projects/robotics/data/hero_map_bags")


def run_curl(url, output_path=None, json_response=False):
    cmd = ["curl", "-b", COOKIE_FILE, "-s", "-L"]
    if json_response:
        cmd.extend(["-H", "Accept: application/json;odata=verbose", url])
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return json.loads(proc.stdout)
    elif output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Use curl with resume (-C -)
        cmd.extend(["-C", "-", url, "-o", str(output_path)])
        proc = subprocess.run(cmd, check=True)
        return proc.returncode


def get_all_items():
    folders_api = f"{BASE_URL}/_api/web/GetFolderByServerRelativeUrl('/personal/runj_pro_vistec_ac_th/Documents/HERO_MAP')/Folders"
    data = run_curl(folders_api, json_response=True)
    folders = data.get("d", {}).get("results", [])

    files_to_download = []
    for f in folders:
        f_url = f["ServerRelativeUrl"]
        f_name = f["Name"]
        files_api = f"{BASE_URL}/_api/web/GetFolderByServerRelativeUrl('{f_url}')/Files"
        fdata = run_curl(files_api, json_response=True)
        for fi in fdata.get("d", {}).get("results", []):
            files_to_download.append({
                "folder": f_name,
                "name": fi["Name"],
                "size": int(fi.get("Length", 0)),
                "server_url": fi["ServerRelativeUrl"]
            })
    return files_to_download


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Fetching file manifest from SharePoint HERO_MAP...")
    files = get_all_items()
    total_size = sum(f["size"] for f in files)
    print(f"Found {len(files)} files across 12 runs. Total Size: {total_size / (1024**3):.2f} GB\n")

    for i, item in enumerate(files, 1):
        target_dir = OUTPUT_DIR / item["folder"]
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / item["name"]
        expected_size = item["size"]

        if target_file.exists() and target_file.stat().st_size == expected_size:
            print(f"[{i}/{len(files)}] Already complete: {item['folder']}/{item['name']}")
            continue

        print(f"[{i}/{len(files)}] Downloading {item['folder']}/{item['name']} ({expected_size / (1024**2):.1f} MB)...")
        download_url = f"{BASE_URL}/_api/web/GetFileByServerRelativeUrl('{item['server_url']}')/$value"

        # Download with curl
        cmd = ["curl", "-b", COOKIE_FILE, "-L", "-C", "-", download_url, "-o", str(target_file), "--progress-bar"]
        try:
            subprocess.run(cmd, check=True)
            print(f"[{i}/{len(files)}] Finished: {item['name']}")
        except subprocess.CalledProcessError as e:
            print(f"Error downloading {item['name']}: {e}")

    print("\nAll downloads completed successfully!")


if __name__ == "__main__":
    main()
