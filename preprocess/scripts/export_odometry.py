#!/usr/bin/env python3
"""
Export /Odometry from ROS 1 / ROS 2 bags into standard TUM and CSV trajectory formats.
Does not require ROS installed; uses 'rosbags' library.
"""

import sys
import csv
from pathlib import Path
import numpy as np

try:
    from rosbags.rosbag1 import Reader as Reader1
    from rosbags.rosbag2 import Reader as Reader2
    from rosbags.typesys import Stores, get_typestore
except ImportError:
    print("Error: 'rosbags' package not installed. Run: pip install rosbags")
    sys.exit(1)


def export_odometry(bag_path_str: str, output_dir_str: str, topic_name: str = "/Odometry"):
    bag_path = Path(bag_path_str)
    out_dir = Path(output_dir_str)
    out_dir.mkdir(parents=True, exist_ok=True)

    is_ros2 = bag_path.is_dir() or bag_path.suffix in [".db3", ".mcap"]
    reader_cls = Reader2 if is_ros2 else Reader1
    store_name = Stores.ROS2_HUMBLE if is_ros2 else Stores.ROS1_NOETIC
    typestore = get_typestore(store_name)

    tum_file = out_dir / "trajectory_tum.txt"
    csv_file = out_dir / "odometry.csv"

    print(f"Reading odometry from: {bag_path.resolve()}")
    print(f"Target topic:         {topic_name}")
    print(f"Output files:         {tum_file.name}, {csv_file.name}")

    count = 0
    poses = []

    with reader_cls(bag_path) as reader:
        conns = [c for c in reader.connections if c.topic == topic_name]
        if not conns:
            print(f"Topic '{topic_name}' not found in bag! Available topics:")
            for t in reader.topics.keys():
                print(f"  {t}")
            return

        for connection, timestamp, rawdata in reader.messages(connections=conns):
            msg = typestore.deserialize_cdr(rawdata, connection.msgtype) if is_ros2 else typestore.deserialize_ros1(rawdata, connection.msgtype)
            
            # Timestamp in fractional seconds
            t_sec = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
            
            # Position
            px = msg.pose.pose.position.x
            py = msg.pose.pose.position.y
            pz = msg.pose.pose.position.z
            
            # Orientation (quaternion)
            qx = msg.pose.pose.orientation.x
            qy = msg.pose.pose.orientation.y
            qz = msg.pose.pose.orientation.z
            qw = msg.pose.pose.orientation.w
            
            # Linear velocity
            vx = msg.twist.twist.linear.x
            vy = msg.twist.twist.linear.y
            vz = msg.twist.twist.linear.z

            poses.append((t_sec, px, py, pz, qx, qy, qz, qw, vx, vy, vz))
            count += 1

    if not poses:
        print("No odometry messages found.")
        return

    # Write TUM format: timestamp x y z qx qy qz qw
    with open(tum_file, "w") as f_tum:
        for p in poses:
            f_tum.write(f"{p[0]:.6f} {p[1]:.6f} {p[2]:.6f} {p[3]:.6f} {p[4]:.6f} {p[5]:.6f} {p[6]:.6f} {p[7]:.6f}\n")

    # Write CSV format
    with open(csv_file, "w", newline="") as f_csv:
        writer = csv.writer(f_csv)
        writer.writerow(["timestamp_sec", "x", "y", "z", "qx", "qy", "qz", "qw", "vx", "vy", "vz"])
        for p in poses:
            writer.writerow(p)

    # Compute summary metrics
    coords = np.array([[p[1], p[2], p[3]] for p in poses])
    diffs = np.diff(coords, axis=0)
    total_distance = np.sum(np.linalg.norm(diffs, axis=1))
    duration = poses[-1][0] - poses[0][0]

    print(f"\nSuccessfully exported {count} poses!")
    print(f"Trajectory Duration: {duration:.2f} seconds")
    print(f"Total Trajectory Length: {total_distance:.3f} meters")
    print(f"Bounding Box [X]: [{coords[:,0].min():.3f}, {coords[:,0].max():.3f}]")
    print(f"Bounding Box [Y]: [{coords[:,1].min():.3f}, {coords[:,1].max():.3f}]")
    print(f"Bounding Box [Z]: [{coords[:,2].min():.3f}, {coords[:,2].max():.3f}]")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python export_odometry.py <bag_path> <output_dir> [topic_name]")
        sys.exit(1)

    topic = sys.argv[3] if len(sys.argv) > 3 else "/Odometry"
    export_odometry(sys.argv[1], sys.argv[2], topic_name=topic)
