#!/usr/bin/env python3
"""
Inspect ROS 1 (.bag) and ROS 2 (.db3 / .mcap) bag files without needing a ROS installation.
Uses the pure-Python 'rosbags' library.
"""

import sys
import os
from pathlib import Path

try:
    from rosbags.rosbag1 import Reader as Reader1
    from rosbags.rosbag2 import Reader as Reader2
except ImportError:
    print("Error: 'rosbags' is not installed. Run: pip install rosbags")
    sys.exit(1)


def inspect_bag(bag_path_str: str):
    path = Path(bag_path_str)
    if not path.exists():
        print(f"Error: Path does not exist: {path}")
        return

    print("=" * 80)
    print(f"INSPECTING BAG: {path.resolve()}")
    print("=" * 80)

    # Determine whether ROS 1 or ROS 2
    is_ros2 = path.is_dir() or path.suffix in [".db3", ".mcap"]

    reader_cls = Reader2 if is_ros2 else Reader1
    bag_type_str = "ROS 2 (Directory / db3 / mcap)" if is_ros2 else "ROS 1 (.bag)"
    print(f"Detected Format: {bag_type_str}\n")

    try:
        with reader_cls(path) as reader:
            duration_sec = (reader.duration / 1e9) if hasattr(reader, "duration") else 0
            start_sec = (reader.start_time / 1e9) if hasattr(reader, "start_time") else 0
            end_sec = (reader.end_time / 1e9) if hasattr(reader, "end_time") else 0

            print(f"Total Messages: {reader.message_count}")
            if duration_sec > 0:
                print(f"Duration:       {duration_sec:.2f} seconds ({duration_sec / 60:.2f} minutes)")
                print(f"Start Time:     {start_sec:.2f}")
                print(f"End Time:       {end_sec:.2f}")

            print("\n" + "-" * 80)
            print(f"{'Topic Name':<45} | {'Message Count':<12} | {'Message Type'}")
            print("-" * 80)

            # Topics and types
            topics = reader.topics
            for topic, topic_info in sorted(topics.items()):
                msg_count = topic_info.msgcount
                msg_type = topic_info.msgtype
                print(f"{topic:<45} | {msg_count:<12} | {msg_type}")

            print("-" * 80)
            print("\nCommon topics to look for:")
            for topic in topics.keys():
                lower = topic.lower()
                if any(k in lower for k in ["image", "color", "rgb"]):
                    print(f"  [Camera RGB]      {topic}")
                elif "depth" in lower:
                    print(f"  [Camera Depth]    {topic}")
                elif any(k in lower for k in ["pointcloud", "points", "lidar"]):
                    print(f"  [LiDAR 3D Cloud]  {topic}")
                elif any(k in lower for k in ["imu", "inertial"]):
                    print(f"  [IMU]             {topic}")
                elif any(k in lower for k in ["odom", "pose", "fast_lio"]):
                    print(f"  [Odometry/Pose]   {topic}")

    except Exception as e:
        print(f"Failed to read as {bag_type_str}: {e}")
        # Try fallback
        alt_cls = Reader1 if is_ros2 else Reader2
        alt_name = "ROS 1" if is_ros2 else "ROS 2"
        print(f"\nAttempting fallback with {alt_name} reader...")
        try:
            with alt_cls(path) as reader:
                print(f"Successfully opened with {alt_name} reader!")
                print(f"Total Messages: {reader.message_count}")
                for topic, topic_info in sorted(reader.topics.items()):
                    print(f"{topic:<45} | {topic_info.msgcount:<12} | {topic_info.msgtype}")
        except Exception as e2:
            print(f"Fallback also failed: {e2}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect_bag.py <path_to_rosbag_file_or_dir>")
        print("Examples:")
        print("  python inspect_bag.py ./run1.bag")
        print("  python inspect_bag.py ./ros2_bag_dir/")
        sys.exit(1)

    inspect_bag(sys.argv[1])
