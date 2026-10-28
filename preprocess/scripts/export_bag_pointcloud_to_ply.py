#!/usr/bin/env python3
"""
Extract registered PointCloud2 scans from recorded FAST-LIO bag into a single merged PLY point cloud for 3DGS initialization.
"""

import sys
from pathlib import Path
import numpy as np

try:
    from rosbags.rosbag2 import Reader
    from rosbags.typesys import Stores, get_typestore
except ImportError:
    print("Error: 'rosbags' not installed. Run: pip install rosbags")
    sys.exit(1)


def export_cloud_to_ply(bag_path_str: str, output_ply_str: str, stride: int = 5):
    bag_path = Path(bag_path_str)
    out_ply = Path(output_ply_str)
    out_ply.parent.mkdir(parents=True, exist_ok=True)

    typestore = get_typestore(Stores.ROS2_HUMBLE)
    pts_list = []

    print(f"Reading /cloud_registered from: {bag_path}")
    with Reader(bag_path) as reader:
        conns = [c for c in reader.connections if c.topic == '/cloud_registered']
        if not conns:
            print("No /cloud_registered topic found in bag!")
            return

        for i, (conn, t, raw) in enumerate(reader.messages(connections=conns)):
            if i % stride != 0:
                continue

            msg = typestore.deserialize_cdr(raw, conn.msgtype)
            point_step = msg.point_step
            dt = np.dtype([('x', '<f4'), ('y', '<f4'), ('z', '<f4'), ('pad', f'V{point_step - 12}')])
            arr = np.frombuffer(msg.data, dtype=dt)
            pts = np.stack([arr['x'], arr['y'], arr['z']], axis=1)
            valid = ~np.isnan(pts).any(axis=1) & ~np.isinf(pts).any(axis=1)
            pts_list.append(pts[valid])

    if not pts_list:
        print("No valid points extracted.")
        return

    all_pts = np.vstack(pts_list)
    print(f"Extracted {len(all_pts)} registered points.")
    print(f"Bounds X: [{all_pts[:,0].min():.3f}, {all_pts[:,0].max():.3f}]")
    print(f"Bounds Y: [{all_pts[:,1].min():.3f}, {all_pts[:,1].max():.3f}]")
    print(f"Bounds Z: [{all_pts[:,2].min():.3f}, {all_pts[:,2].max():.3f}]")

    with open(out_ply, 'w') as f:
        f.write('ply\nformat ascii 1.0\n')
        f.write(f'element vertex {len(all_pts)}\n')
        f.write('property float x\nproperty float y\nproperty float z\nend_header\n')
        for pt in all_pts:
            f.write(f'{pt[0]:.4f} {pt[1]:.4f} {pt[2]:.4f}\n')

    print(f"Saved PLY point cloud: {out_ply}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python export_bag_pointcloud_to_ply.py <recorded_bag> <output.ply> [stride]")
        sys.exit(1)

    s = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    export_cloud_to_ply(sys.argv[1], sys.argv[2], stride=s)
