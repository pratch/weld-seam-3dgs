# Project Onboarding & ROS Bag Guide: HERO 2.1 Robotics Inspection

This guide explains the project setup, downloaded assets, how to work with ROS bag files (even without ROS installed), and next steps for collaborating with **Run Janna** and the robotics team.

---

## 1. Directory Structure & Status

```
/ist-nas/users/pratchp/projects/robotics/
├── data/
│   ├── hero_map_bags/                      # 12 ROS 2 bags (30.3 GB) from VISTEC SharePoint
│   ├── gdrive_data/                        # Videos & screencasts from Google Drive
│   └── links.txt                           # Source links
├── doc/
│   ├── PROJECT_ONBOARDING_GUIDE.md         # This guide
│   ├── 3DGS_INTEGRATION_AND_PROPOSAL.md    # Technical proposal on 3DGS
│   └── papers/                             # IROS 2026 paper PDF & PAPER_SUMMARY.md
├── experiments/                            # Structured day-by-day experiment folders
├── preprocess/                             # FAST-LIO2 SLAM, pose interpolation & pointcloud tools
├── inspect_bag.py                          # Python utility to inspect ROS 1 / ROS 2 bag files
└── extract_bag_images.py                   # Python utility to export frames for 3DGS training
```

---

## 2. Status of Downloaded Links

### Link 1: Microsoft OneDrive / SharePoint Link (HERO_MAP)
- **URL:** `https://vistec-my.sharepoint.com/:f:/g/personal/runj_pro_vistec_ac_th/...`
- **Status:** **Public access authenticated & Downloading in background!**
  - Successfully authenticated with guest permissions and retrieved file manifest for all **12 experimental runs** (24 files, total **30.30 GB**).
  - Background downloader script [`download_hero_map.py`](file:///ist-nas/users/pratchp/projects/robotics/download_hero_map.py) is actively streaming all `.db3` and `metadata.yaml` files into [`hero_map_bags/`](file:///ist-nas/users/pratchp/projects/robotics/hero_map_bags).
  - The 12 datasets correspond to the experiments in the paper:
    - **Longitudinal seams:** `livox_record_long1`, `livox_record_long2`, `livox_record_long3`
    - **Longitudinal with defect markers:** `livox_record_longdefect1`, `livox_record_longdefect2`, `livox_record_longdefect3`
    - **Circumferential seams:** `livox_record_cir1`, `livox_record_cir2`, `livox_record_cir3`
    - **Circumferential with defect markers:** `livox_record_cirdefect1`, `livox_record_cirdefect2`, `livox_record_cirdefect3`

### Link 2: Google Drive Shared Folder
- **URL:** `https://drive.google.com/drive/folders/1idxRgIBrsVxs5Fe26GUdQMAuyHd6PFzO`
- **Status:** **Successfully downloaded 100% into `./gdrive_data/`** using `gdown`.
  - Contains demonstration videos and RViz inspection screencasts.

---

## 3. What is a ROS Bag & How to Open It?

### What is a ROS Bag?
A **ROS bag** (`.bag` for ROS 1, or `.db3`/`.mcap` for ROS 2) is a binary container file that records time-synchronized sensor streams published across ROS topics:
- **RGB and Depth images:** e.g., `/camera/color/image_raw`, `/camera/depth/image_rect_raw`
- **3D LiDAR scans:** e.g., `/livox/lidar`, `/cloud_registered`
- **IMU data:** e.g., `/livox/imu`
- **Odometry & transforms:** e.g., `/Odometry`, `/tf`, `/tf_static`

---

### Method 1: Instant Inspection via Included Python Tool (No ROS Needed)
We installed the pure-Python `rosbags` library and created a command-line inspector.

To inspect topics, message counts, and timestamps in any bag file:
```bash
python inspect_bag.py <path_to_bag_file>
```
*Example output:*
```text
================================================================================
INSPECTING BAG: /path/to/hero_inspection.bag
================================================================================
Detected Format: ROS 1 (.bag)
Total Messages: 15420
Duration: 85.30 seconds (1.42 minutes)
--------------------------------------------------------------------------------
Topic Name                                    | Message Count| Message Type
--------------------------------------------------------------------------------
/camera/color/image_raw                       | 2560         | sensor_msgs/Image
/camera/depth/image_rect_raw                  | 2560         | sensor_msgs/Image
/livox/lidar                                  | 853          | livox_ros_driver2/CustomMsg
/Odometry                                     | 8530         | nav_msgs/Odometry
/tf                                           | 8530         | tf2_msgs/TFMessage
```

---

### Method 2: Extracting Frames for 3DGS Training (No ROS Needed)
To export the RGB frames into PNG images with accurate timestamps:
```bash
python extract_bag_images.py <path_to_bag> <image_topic> <output_folder> [max_frames] [stride]
```
*Example:*
```bash
python extract_bag_images.py hero_run.bag /camera/color/image_raw ./dataset/images 1000 2
```

---

### Method 3: Graphical Visualization using Foxglove Studio (Highly Recommended!)
You do **not** need to install full ROS to view 3D point clouds and camera streams interactively.

1. **Web App (Zero Installation):**
   - Open your browser to [https://studio.foxglove.dev/](https://studio.foxglove.dev/).
   - Click **Open local file** and drag-and-drop the `.bag`, `.db3`, or `.mcap` file.
   - Add panels: **3D Scene** (to see LiDAR point clouds and robot trajectory) and **Image** (to view camera feed).
2. **Desktop App:**
   - Download the desktop version from [foxglove.dev/download](https://foxglove.dev/download).

---

### Method 4: Native ROS / RViz (If full ROS environment is preferred)
If you wish to use native ROS 2 tools:
```bash
# In an environment with ROS 2 installed:
ros2 bag info <bag_name>
ros2 bag play <bag_name>
rviz2
```
Or via Docker:
```bash
docker run -it --net=host -v $(pwd):/data osrf/ros:humble-desktop
ros2 bag info /data/<bag_name>
```

---

## 4. Summary of Key Files to Review

1. [PAPER_SUMMARY.md](file:///ist-nas/users/pratchp/projects/robotics/doc/papers/PAPER_SUMMARY.md) — Comprehensive technical breakdown of the algorithm, hardware, and results.
2. [3DGS_INTEGRATION_AND_PROPOSAL.md](file:///ist-nas/users/pratchp/projects/robotics/doc/3DGS_INTEGRATION_AND_PROPOSAL.md) — How 3DGS overcomes thin structure and specularity limitations, and meeting talking points.
3. [inspect_bag.py](file:///ist-nas/users/pratchp/projects/robotics/inspect_bag.py) — ROS bag inspection script.
4. [extract_bag_images.py](file:///ist-nas/users/pratchp/projects/robotics/extract_bag_images.py) — Image extractor for 3DGS dataset creation.
