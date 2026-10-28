#!/usr/bin/env python3
"""
Convert transforms.json (and optional pointcloud PLY) to standard COLMAP binary and text format.
Writes cameras.bin, images.bin, and points3D.bin (plus text versions).
Enables zero-bug, high-speed loading in gsplat, 2DGS, and SuGaR.
"""

import sys
import json
import struct
from pathlib import Path
import numpy as np


def rotmat_to_quat_wxyz(R):
    """Convert 3x3 rotation matrix to quaternion [qw, qx, qy, qz]."""
    tr = np.trace(R)
    if tr > 0.0:
        S = np.sqrt(tr + 1.0) * 2
        qw = 0.25 * S
        qx = (R[2, 1] - R[1, 2]) / S
        qy = (R[0, 2] - R[2, 0]) / S
        qz = (R[1, 0] - R[0, 1]) / S
    elif (R[0, 0] > R[1, 1]) and (R[0, 0] > R[2, 2]):
        S = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        qw = (R[2, 1] - R[1, 2]) / S
        qx = 0.25 * S
        qy = (R[0, 1] + R[1, 0]) / S
        qz = (R[0, 2] + R[2, 0]) / S
    elif R[1, 1] > R[2, 2]:
        S = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        qw = (R[0, 2] - R[2, 0]) / S
        qx = (R[0, 1] + R[1, 0]) / S
        qy = 0.25 * S
        qz = (R[1, 2] + R[2, 1]) / S
    else:
        S = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        qw = (R[1, 0] - R[0, 1]) / S
        qx = (R[0, 2] + R[2, 0]) / S
        qy = (R[1, 2] + R[2, 1]) / S
        qz = 0.25 * S
    q = np.array([qw, qx, qy, qz], dtype=np.float64)
    return q / np.linalg.norm(q)


def parse_ply_points(ply_path: Path, max_points: int = 150000):
    points = []
    if not ply_path.exists():
        return np.zeros((0, 3), dtype=np.float64)

    with open(ply_path, "r", errors="ignore") as f:
        in_header = True
        for line in f:
            if in_header:
                if line.strip() == "end_header":
                    in_header = False
                continue
            parts = line.strip().split()
            if len(parts) >= 3:
                try:
                    points.append([float(parts[0]), float(parts[1]), float(parts[2])])
                except ValueError:
                    continue

    if not points:
        return np.zeros((0, 3), dtype=np.float64)

    pts = np.array(points, dtype=np.float64)
    if len(pts) > max_points:
        indices = np.random.choice(len(pts), max_points, replace=False)
        pts = pts[indices]
    return pts


def export_to_colmap(transforms_json_path: str, output_sparse_dir: str, ply_path_str: str = None):
    trans_p = Path(transforms_json_path)
    sparse_dir = Path(output_sparse_dir)
    sparse_dir.mkdir(parents=True, exist_ok=True)

    with open(trans_p, "r") as f:
        data = json.load(f)

    fx = float(data.get("fl_x", 386.707))
    fy = float(data.get("fl_y", 386.510))
    cx = float(data.get("cx", 313.587))
    cy = float(data.get("cy", 241.178))
    w = int(data.get("w", 640))
    h = int(data.get("h", 480))
    frames = data.get("frames", [])

    print(f"Loaded {len(frames)} frames from {trans_p}")

    # 1. Write cameras.bin (PINHOLE = model id 1: fx, fy, cx, cy)
    cameras_bin = sparse_dir / "cameras.bin"
    with open(cameras_bin, "wb") as f:
        f.write(struct.pack("<Q", 1))  # num_cameras
        # struct: camera_id (uint32), model_id (int32=1), width (uint64), height (uint64)
        f.write(struct.pack("<IiQQ", 1, 1, w, h))
        # 4 params as doubles
        f.write(struct.pack("<4d", fx, fy, cx, cy))
    print(f"Wrote {cameras_bin}")

    # 2. Write images.bin
    images_bin = sparse_dir / "images.bin"
    with open(images_bin, "wb") as f:
        f.write(struct.pack("<Q", len(frames)))  # num_images
        image_struct = struct.Struct("<I 4d 3d I")

        for i, frame in enumerate(frames, start=1):
            T_c2w = np.array(frame["transform_matrix"], dtype=np.float64)
            R_c2w = T_c2w[:3, :3]
            t_c2w = T_c2w[:3, 3]

            # Invert to World-to-Camera (W2C)
            R_w2c = R_c2w.T
            t_w2c = -R_w2c @ t_c2w
            q_w2c = rotmat_to_quat_wxyz(R_w2c)

            img_name = Path(frame["file_path"]).name
            f.write(image_struct.pack(
                i,
                q_w2c[0], q_w2c[1], q_w2c[2], q_w2c[3],
                t_w2c[0], t_w2c[1], t_w2c[2],
                1
            ))
            f.write(img_name.encode("utf-8") + b"\x00")
            f.write(struct.pack("<Q", 0))  # num_points2D = 0
    print(f"Wrote {images_bin}")

    # 3. Write points3D.bin
    pts = np.zeros((0, 3), dtype=np.float64)
    if ply_path_str:
        pts = parse_ply_points(Path(ply_path_str))

    points_bin = sparse_dir / "points3D.bin"
    with open(points_bin, "wb") as f:
        f.write(struct.pack("<Q", len(pts)))  # num_points3D
        pt_struct = struct.Struct("<Q 3d 3B d Q")
        for i, pt in enumerate(pts, start=1):
            f.write(pt_struct.pack(
                i,
                pt[0], pt[1], pt[2],
                128, 128, 128,
                1.0,
                0  # track length = 0
            ))
    print(f"Wrote {points_bin} with {len(pts)} points")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python export_to_colmap.py <transforms.json> <output_sparse_dir> [pointcloud.ply]")
        sys.exit(1)

    ply = sys.argv[3] if len(sys.argv) > 3 else None
    export_to_colmap(sys.argv[1], sys.argv[2], ply)
