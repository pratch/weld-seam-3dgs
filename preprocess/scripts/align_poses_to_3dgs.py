#!/usr/bin/env python3
"""
Align FAST-LIO2 Odometry with Extracted Camera Frames to generate transforms.json (standard 3DGS format).
Pure Python + NumPy implementation (Zero external dependencies).
"""

import sys
import json
import re
from pathlib import Path
import numpy as np


def parse_timestamp_from_filename(filename: str):
    m = re.search(r"(\d{10,20})", filename)
    if m:
        ts_val = int(m.group(1))
        # Bag timestamps are in nanoseconds (e.g. 223367687584 ns = 223.368 s)
        if ts_val > 1e8:
            return ts_val * 1e-9
        return float(ts_val)
    return None


def quat_to_rotmat(q):
    """Convert quaternion [x, y, z, w] to 3x3 rotation matrix."""
    x, y, z, w = q / np.linalg.norm(q)
    return np.array([
        [1.0 - 2.0 * (y*y + z*z), 2.0 * (x*y - z*w),       2.0 * (x*z + y*w)],
        [2.0 * (x*y + z*w),       1.0 - 2.0 * (x*x + z*z), 2.0 * (y*z - x*w)],
        [2.0 * (x*z - y*w),       2.0 * (y*z + x*w),       1.0 - 2.0 * (x*x + y*y)]
    ])


def quat_slerp(q0, q1, t):
    """Spherical linear interpolation between two quaternions [x, y, z, w]."""
    q0 = q0 / np.linalg.norm(q0)
    q1 = q1 / np.linalg.norm(q1)
    dot = np.dot(q0, q1)

    if dot < 0.0:
        q1 = -q1
        dot = -dot

    if dot > 0.9995:
        res = q0 + t * (q1 - q0)
        return res / np.linalg.norm(res)

    theta_0 = np.arccos(np.clip(dot, -1.0, 1.0))
    sin_theta_0 = np.sin(theta_0)
    theta_t = theta_0 * t
    s0 = np.sin(theta_0 - theta_t) / sin_theta_0
    s1 = np.sin(theta_t) / sin_theta_0
    return s0 * q0 + s1 * q1


def generate_transforms_json(
    images_dir_str: str,
    odometry_csv_str: str,
    output_json_str: str,
    fx: float = 386.707,
    fy: float = 386.510,
    cx: float = 313.587,
    cy: float = 241.178,
    width: int = 640,
    height: int = 480,
    t_cam_body = (0.0, 0.0, 0.0),
    q_cam_body = (0.0, 0.0, 0.0, 1.0)
):
    images_dir = Path(images_dir_str)
    odom_csv = Path(odometry_csv_str)
    out_json = Path(output_json_str)
    out_json.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading odometry from {odom_csv}...")
    odom_data = np.loadtxt(odom_csv, delimiter=",", skiprows=1)
    odom_times = odom_data[:, 0]
    odom_pos = odom_data[:, 1:4]
    odom_quat = odom_data[:, 4:8]

    # Hand-eye extrinsic transformation matrix (Camera to Body)
    T_cam_body = np.eye(4)
    T_cam_body[:3, :3] = quat_to_rotmat(np.array(q_cam_body))
    T_cam_body[:3, 3] = t_cam_body

    # Collect images
    image_files = sorted([p for p in images_dir.iterdir() if p.suffix.lower() in [".png", ".jpg", ".jpeg"]])
    print(f"Found {len(image_files)} images in {images_dir}.")

    frames = []
    min_t, max_t = odom_times[0], odom_times[-1]
    skipped = 0

    for img_path in image_files:
        t_img = parse_timestamp_from_filename(img_path.name)
        if t_img is None:
            continue

        if t_img < min_t or t_img > max_t:
            skipped += 1
            continue

        # Find interpolation bracket
        idx = np.searchsorted(odom_times, t_img) - 1
        idx = max(0, min(idx, len(odom_times) - 2))
        
        t0 = odom_times[idx]
        t1 = odom_times[idx + 1]
        alpha = (t_img - t0) / (t1 - t0) if t1 > t0 else 0.0
        alpha = np.clip(alpha, 0.0, 1.0)

        # Interpolate position & rotation
        pos_interp = (1.0 - alpha) * odom_pos[idx] + alpha * odom_pos[idx + 1]
        quat_interp = quat_slerp(odom_quat[idx], odom_quat[idx + 1], alpha)
        rot_interp = quat_to_rotmat(quat_interp)

        # Robot Body to World matrix
        T_body_w = np.eye(4)
        T_body_w[:3, :3] = rot_interp
        T_body_w[:3, 3] = pos_interp

        # Camera to World matrix: T_cam_w = T_body_w @ T_cam_body
        T_cam_w = T_body_w @ T_cam_body

        import os
        frames.append({
            "file_path": os.path.relpath(img_path, out_json.parent),
            "timestamp": t_img,
            "transform_matrix": T_cam_w.tolist()
        })

    print(f"Successfully aligned {len(frames)} frames ({skipped} frames outside odometry time range).")

    data = {
        "camera_model": "PINHOLE",
        "fl_x": fx,
        "fl_y": fy,
        "cx": cx,
        "cy": cy,
        "w": width,
        "h": height,
        "frames": frames
    }

    with open(out_json, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Saved 3DGS transforms configuration to: {out_json}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python align_poses_to_3dgs.py <images_dir> <odometry.csv> <output_transforms.json>")
        sys.exit(1)

    generate_transforms_json(sys.argv[1], sys.argv[2], sys.argv[3])
