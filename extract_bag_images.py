#!/usr/bin/env python3
"""
Extract RGB and Depth images from ROS 1 / ROS 2 bags into PNGs for 3DGS training.
Pure Python - does not require ROS installed.
"""

import sys
import os
from pathlib import Path
import numpy as np
import cv2

from rosbags.rosbag1 import Reader as Reader1
from rosbags.rosbag2 import Reader as Reader2
from rosbags.typesys import Stores, get_typestore


def extract_images(bag_path_str: str, topic_name: str, output_dir_str: str, max_frames: int = 500, stride: int = 1):
    path = Path(bag_path_str)
    out_dir = Path(output_dir_str)
    out_dir.mkdir(parents=True, exist_ok=True)

    is_ros2 = path.is_dir() or path.suffix in [".db3", ".mcap"]
    reader_cls = Reader2 if is_ros2 else Reader1
    store_name = Stores.ROS2_HUMBLE if is_ros2 else Stores.ROS1_NOETIC
    typestore = get_typestore(store_name)

    print(f"Reading:      {path.resolve()}")
    print(f"Format:       {'ROS 2' if is_ros2 else 'ROS 1'}")
    print(f"Target Topic: {topic_name}")
    print(f"Output Dir:   {out_dir.resolve()}")

    count = 0
    saved = 0

    with reader_cls(path) as reader:
        connections = [x for x in reader.connections if x.topic == topic_name]
        if not connections:
            print(f"Topic '{topic_name}' not found! Available topics:")
            for t in reader.topics.keys():
                print(f"  {t}")
            return

        for connection, timestamp, rawdata in reader.messages(connections=connections):
            count += 1
            if count % stride != 0:
                continue

            msg = typestore.deserialize_cdr(rawdata, connection.msgtype) if is_ros2 else typestore.deserialize_ros1(rawdata, connection.msgtype)
            try:
                h, w = msg.height, msg.width
                encoding = msg.encoding

                if encoding in ["bgr8", "rgb8"]:
                    img = np.frombuffer(msg.data, dtype=np.uint8).reshape((h, w, 3))
                    if encoding == "rgb8":
                        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                elif encoding in ["mono8", "8UC1"]:
                    img = np.frombuffer(msg.data, dtype=np.uint8).reshape((h, w))
                elif encoding in ["16UC1", "mono16"]:
                    # 16-bit depth in millimeters
                    img = np.frombuffer(msg.data, dtype=np.uint16).reshape((h, w))
                elif encoding in ["32FC1"]:
                    # 32-bit float depth in meters -> convert to mm uint16
                    img_f = np.frombuffer(msg.data, dtype=np.float32).reshape((h, w))
                    img = (img_f * 1000.0).astype(np.uint16)
                else:
                    print(f"Unsupported encoding: {encoding}")
                    continue

                filename = out_dir / f"frame_{saved:05d}_{timestamp}.png"
                cv2.imwrite(str(filename), img)
                saved += 1

                if saved % 50 == 0:
                    print(f"Extracted {saved} frames...")

                if saved >= max_frames:
                    print(f"Reached limit of {max_frames} frames.")
                    break
            except Exception as e:
                print(f"Error decoding frame {count}: {e}")

    print(f"\nDone! Extracted {saved} frames to {out_dir}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python extract_bag_images.py <bag_path> <image_topic> <output_dir> [max_frames] [stride]")
        print("Example: python extract_bag_images.py data/hero_map_bags/livox_record_long119700101_001455 /camera/color/image_raw ./extracted_rgb 500 2")
        sys.exit(1)

    max_f = int(sys.argv[4]) if len(sys.argv) > 4 else 1000
    stride_step = int(sys.argv[5]) if len(sys.argv) > 5 else 1
    extract_images(sys.argv[1], sys.argv[2], sys.argv[3], max_frames=max_f, stride=stride_step)
