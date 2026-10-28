# Preprocessing Pipeline: FAST-LIO2 Odometry & Sensor Alignment for 3DGS

This folder houses the complete offline SLAM and sensor preprocessing pipeline for the **HERO 2.1** robotics inspection dataset. It processes raw Livox Mid-360 LiDAR + IMU streams using **FAST-LIO2** to produce drift-free, 6-DoF metric camera trajectories and registered point clouds for Gaussian Splatting (3DGS).

---

## 1. Directory Structure

```text
preprocess/
├── README.md                      # Pipeline guide & documentation
├── config/
│   └── mid360_hero.yaml           # Tuned FAST-LIO2 config for Livox Mid-360 on HERO 2.1
├── scripts/
│   ├── run_fast_lio_offline.sh    # Automated runner (launches FAST-LIO2, plays bag, records outputs)
│   ├── export_odometry.py         # Converts recorded /Odometry to TUM & CSV trajectory formats
│   ├── align_poses_to_3dgs.py     # Interpolates poses to camera timestamps & outputs transforms.json
│   └── export_pcd_to_ply.py       # Converts registered PCD point clouds to PLY for 3DGS initialization
├── docker/
│   ├── Dockerfile                 # Self-contained ROS 2 Humble + FAST-LIO2 + Livox driver environment
│   └── docker-compose.yml         # One-command Docker execution setup
└── output/                        # Default output destination
    ├── odometry/                  # 6-DoF trajectories (TUM format, CSV, transforms.json)
    ├── cloud_registered/          # Global registered point clouds (.pcd, .ply)
    └── images/                    # Extracted synchronized RGB/depth frames
```

---

## 2. Environment Setup Options

FAST-LIO2 requires ROS 2 Humble, PCL, and `livox_ros_driver2`. Choose the option matching your system:

### Option A: Apptainer / Singularity (Recommended for IST-NAS)
Because `apptainer` is installed on the NAS and runs without `sudo` / root permissions:
```bash
# 1. Build or pull the ROS 2 Humble image
apptainer build fast_lio2.sif docker://osrf/ros:humble-desktop

# 2. Run an interactive shell inside the container with NAS mounted
apptainer shell --nv --bind /ist-nas:/ist-nas fast_lio2.sif
```

### Option B: Docker (Local Workstations)
If you have Docker daemon access:
```bash
cd preprocess/docker
docker compose build
docker compose run --rm fast_lio2
```

### Option C: Native ROS 2 Humble
If running on a system with native ROS 2 Humble installed:
```bash
# Clone and build FAST-LIO2 in your colcon workspace
mkdir -p ~/ros2_ws/src && cd ~/ros2_ws/src
git clone https://github.com/Livox-SDK/livox_ros_driver2.git
git clone https://github.com/Ericsii/FAST_LIO_ROS2.git fast_lio
cd ~/ros2_ws && colcon build --symlink-install
source install/setup.bash
```

---

## 3. End-to-End Processing Workflow

### Step 1: Run FAST-LIO2 on the Bag File
Run the automated offline script on any bag file:
```bash
./preprocess/scripts/run_fast_lio_offline.sh \
    data/hero_map_bags/livox_record_longdefect119700101_000342 \
    longdefect1
```
This executes:
1. Launches the FAST-LIO2 node with [mid360_hero.yaml](file:///ist-nas/users/pratchp/projects/robotics/preprocess/config/mid360_hero.yaml).
2. Plays the Livox LiDAR (`/livox/lidar`) and IMU (`/livox/imu`) streams.
3. Records the resulting `/Odometry` and `/cloud_registered` topics into `preprocess/output/odometry/longdefect1/`.
4. Converts the odometry into standard TUM format (`trajectory_tum.txt`) and CSV (`odometry.csv`).

---

### Step 2: Extract RGB Video Frames
Extract synchronized RGB frames from the bag into the images folder:
```bash
python3 extract_bag_images.py \
    data/hero_map_bags/livox_record_longdefect119700101_000342 \
    /camera/color/image_raw \
    preprocess/output/images/longdefect1 \
    1000 1
```

---

### Step 3: Align Odometry Poses to Camera Frames (`transforms.json`)
Synchronize the camera frames with the FAST-LIO2 odometry using SLERP interpolation:
```bash
python3 preprocess/scripts/align_poses_to_3dgs.py \
    preprocess/output/images/longdefect1 \
    preprocess/output/odometry/longdefect1/odometry.csv \
    preprocess/output/odometry/longdefect1/transforms.json
```
The generated `transforms.json` contains:
- Exact camera intrinsics ($f_x, f_y, c_x, c_y$, resolution $640 \times 480$).
- Metric $4 \times 4$ camera-to-world extrinsic transformation matrix for every frame.
- Direct drop-in compatibility with 3DGS frameworks (`gaussian-splatting`, `gsplat`, `nerfstudio`).

---

### Step 4: Convert Point Cloud Map for 3DGS Initialization
Convert the saved FAST-LIO registered `.pcd` point cloud into `.ply`:
```bash
python3 preprocess/scripts/export_pcd_to_ply.py \
    preprocess/output/cloud_registered/longdefect1/scans.pcd \
    preprocess/output/cloud_registered/longdefect1/initial_points.ply
```
This provides the **true metric sparse point cloud** used to initialize 3D Gaussian centers, eliminating the need for COLMAP point clouds!

---

## 4. Output Data Format Reference

| Output File | Format | Purpose |
|---|---|---|
| `odometry.csv` | CSV | Raw time-series position $[x,y,z]$, quaternion $[q_x,q_y,q_z,q_w]$, and velocities |
| `trajectory_tum.txt` | TUM ASCII | Standard format for trajectory evaluation (via `evo`) |
| `transforms.json` | JSON | Standard NeRF/3DGS format containing intrinsics & frame poses |
| `initial_points.ply` | PLY | Registered sparse 3D point cloud for 3D Gaussian initialization |
| `images/*.png` | PNG ($640 \times 480$) | Synchronized RGB inspection frames |
