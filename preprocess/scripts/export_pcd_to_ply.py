#!/usr/bin/env python3
"""
Convert FAST-LIO output PCD point cloud to standard PLY format for 3DGS initialization.
Can run with open3d or pure-python/numpy fallback.
"""

import sys
from pathlib import Path
import numpy as np


def convert_pcd_to_ply(pcd_path_str: str, ply_output_str: str):
    pcd_path = Path(pcd_path_str)
    ply_path = Path(ply_output_str)
    ply_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading PCD: {pcd_path}")
    try:
        import open3d as o3d
        pcd = o3d.io.read_point_cloud(str(pcd_path))
        num_pts = len(pcd.points)
        print(f"Loaded {num_pts} points via Open3D.")
        o3d.io.write_point_cloud(str(ply_path), pcd, write_ascii=False)
        print(f"Saved binary PLY: {ply_path}")
        return
    except ImportError:
        print("Open3D not available, parsing PCD header manually...")

    # Manual PCD parser fallback
    with open(pcd_path, "rb") as f:
        header = []
        while True:
            line = f.readline().decode("ascii", errors="ignore").strip()
            header.append(line)
            if line.startswith("DATA"):
                data_mode = line.split()[1]
                break

        fields = {}
        for h in header:
            parts = h.split()
            if parts[0] == "FIELDS":
                fields["names"] = parts[1:]
            elif parts[0] == "POINTS":
                fields["count"] = int(parts[1])

        print(f"PCD Header: {fields['count']} points, data_mode={data_mode}")
        if data_mode == "ascii":
            data = np.loadtxt(f)
            pts = data[:, :3]
        elif data_mode == "binary":
            raw = f.read()
            # Standard xyz float32 (12 bytes) + possible intensity/ring
            record_size = len(raw) // fields["count"]
            dt = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4")] + [("pad", f"V{record_size - 12}")])
            arr = np.frombuffer(raw, dtype=dt)
            pts = np.stack([arr["x"], arr["y"], arr["z"]], axis=1)

    print(f"Extracted {len(pts)} points. Writing PLY...")
    with open(ply_path, "w") as f_ply:
        f_ply.write("ply\n")
        f_ply.write("format ascii 1.0\n")
        f_ply.write(f"element vertex {len(pts)}\n")
        f_ply.write("property float x\n")
        f_ply.write("property float y\n")
        f_ply.write("property float z\n")
        f_ply.write("end_header\n")
        for pt in pts:
            f_ply.write(f"{pt[0]:.4f} {pt[1]:.4f} {pt[2]:.4f}\n")

    print(f"Saved PLY to {ply_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python export_pcd_to_ply.py <input.pcd> <output.ply>")
        sys.exit(1)
    convert_pcd_to_ply(sys.argv[1], sys.argv[2])
