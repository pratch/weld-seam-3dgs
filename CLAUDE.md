# Project Guidelines & Agent Instructions: HERO 2.1 3DGS Inspection

## 1. Project Overview & Research Mission

* **Platform:** HERO 2.1 magnetic-wheel climbing robot inspecting industrial ferromagnetic pressure vessels (oil & gas, PTTEP/VISTEC, target IROS 2026).
* **Sensors:**
  * **Intel RealSense D405:** High-res RGB-D at short standoff ($8\text{--}10\text{ cm}$).
  * **Livox Mid-360 LiDAR + IMU:** 3D LiDAR running **FAST-LIO2** LiDAR-Inertial Odometry onboard NVIDIA Jetson Orin NX.
* **Core Research Problem:**
  * The current IROS paper detects seam centerlines via 1D depth filtering, but generates only a **synthetic geometric ribbon of random noise** around a 1D spline ($p_{\text{dense}} = p_{\text{int}} + \epsilon$). It does **not** perform true 3D surface reconstruction.
  * Active IR depth cameras suffer from severe multi-path reflections and dropouts on shiny curved metal.
  * LiDAR spot size is too coarse (~cm level) to resolve millimeter-scale weld crowns, toe angles, ripples, or hairline cracks.
* **Our Solution (3DGS + FAST-LIO2):**
  * We use **3D Gaussian Splatting (3DGS)** and surface splatting (2DGS / SuGaR) to build true sub-millimeter, photorealistic 3D digital twins of weld seams and defects.
  * **The Core Synergy:** Traditional 3DGS relies on COLMAP SfM, which fails completely on repetitive, shiny metal plates. We **bypass COLMAP entirely** by using drift-free 6-DoF metric poses from **FAST-LIO2** and initialize Gaussians from registered LiDAR point clouds.

---

## 2. Repository Layout & Conventions

```text
/ist-nas/users/pratchp/projects/robotics/
├── data/                               # Raw data, large inputs, bag files (DO NOT commit large files to git)
│   ├── hero_map_bags/                  # 12 ROS 2 bags (.db3, metadata.yaml) from VISTEC SharePoint
│   ├── gdrive_data/                    # Videos and screencasts from Google Drive
│   └── links.txt                       # Raw download links and data source references
├── doc/                                # High-level project documentation & background
│   ├── PROJECT_ONBOARDING_GUIDE.md     # ROS bag inspection, Foxglove Studio usage, topic lists
│   ├── 3DGS_INTEGRATION_AND_PROPOSAL.md# Theoretical breakdown, 3DGS math, meeting talking points
│   └── papers/                         # Reference literature
│       ├── Emailing 1142_IROS_2026_paper.pdf # Original IROS 2026 submission
│       └── PAPER_SUMMARY.md            # Detailed technical breakdown of the IROS paper
├── experiments/                        # Day-by-day experiment records (see Protocol below)
│   └── YYYYMMDD_<exp_name>/            # e.g., 20261028_baseline_3dgs_longdefect/
├── preprocess/                         # Subtask: Sensor preprocessing, SLAM & 3DGS format conversion
│   ├── README.md                       # Complete preprocessing guide
│   ├── config/mid360_hero.yaml         # FAST-LIO2 parameters tuned for HERO 2.1 Livox Mid-360
│   ├── scripts/                        # run_fast_lio_offline.sh, align_poses_to_3dgs.py, export_pcd_to_ply.py
│   ├── docker/                         # Dockerfile and docker-compose.yml for ROS 2 Humble + FAST-LIO2
│   ├── fast_lio2.sif                   # Self-contained Apptainer/Singularity container for NAS execution
│   └── output/                         # Processed odometry, transforms.json, and registered point clouds
├── visualizer/                         # Core tool: Interactive 3D Web Visualizer (Three.js)
│   ├── index.html                      # 3D camera trajectory, frustum snapping, split curtain slider
│   ├── style.css                       # Modern dark glassmorphism UI
│   ├── app.js                          # Three.js 3D viewport, raycaster, camera animation & image sync
│   └── scene_data.json                 # Aligned camera poses & metadata for inspection
├── inspect_bag.py                      # Root utility: inspect bag topics/counts without installing ROS
├── extract_bag_images.py               # Root utility: export synchronized camera frames from bags
├── download_hero_map.py                # Root utility: automated downloader for SharePoint bag datasets
├── CLAUDE.md                           # This file (instructions & architecture rules for agents)
└── AGENTS.md                           # Symlink to CLAUDE.md for multi-agent support
```

---

## 3. Experimentation Protocol (`experiments/`)

Whenever conducting a new model run, ablation study, or benchmark:
1. Create a dedicated folder: `experiments/<YYYYMMDD>_<experiment_name>/` (e.g. `experiments/20261028_longdefect1_nerfstudio/`).
2. Inside every experiment directory, there **MUST** be a `README.md` containing:
   * **Objective & Hypothesis:** What are we testing?
   * **Dataset / Bag:** Exact bag path and frame range used (e.g. `data/hero_map_bags/livox_record_longdefect1...`).
   * **Configuration & Code:** Exact scripts, hyperparameters, or modified code used.
   * **Execution Command:** Full bash command to reproduce the experiment.
   * **Results & Metrics:** Key metrics (PSNR, SSIM, LPIPS, reconstruction quality, defect visibility) and screenshots/renders.
   * **Key Takeaways & Next Steps:** What did we learn?
3. Save experiment-specific scripts, configurations, and small evaluation plots inside this folder. Store large checkpoints or rendered datasets in designated storage (or `output/` subfolders), referencing them in the `README.md`.

---

## 4. Code & Subtask Structure Rules

1. **Subtasks vs. Root Code:**
   * Specialized multi-step pipelines belong in a dedicated subtask directory (e.g. `preprocess/`, `reconstruction/`, `evaluation/`).
   * Lightweight, frequently used entry-point tools and inspectors live in the project root (e.g. `inspect_bag.py`, `extract_bag_images.py`).
2. **Paths:**
   * Always use relative paths from the project root or construct paths using `pathlib.Path(__file__).resolve().parents[...]`.
   * Never hardcode machine-specific paths outside `/ist-nas/users/pratchp/projects/robotics`.
3. **Environment Execution:**
   * For ROS 2 and FAST-LIO2, use the Apptainer container:
     ```bash
     apptainer shell --nv --bind /ist-nas:/ist-nas preprocess/fast_lio2.sif
     ```
     or the Docker Compose environment in `preprocess/docker/`.
   * For Python bag inspection and image extraction, use the local python environment (`rosbags`, `cv2`, `numpy`, `scipy`).

---

## 5. Standard Processing Workflow

1. **Step 1 (Extract Images):**
   ```bash
   python3 extract_bag_images.py data/hero_map_bags/<bag_name> /camera/color/image_raw preprocess/output/images/<run_id> 1000 1
   ```
2. **Step 2 (Odometry via FAST-LIO2):**
   ```bash
   ./preprocess/scripts/run_fast_lio_offline.sh data/hero_map_bags/<bag_name> <run_id>
   ```
3. **Step 3 (Align Poses & Intrinsics to `transforms.json`):**
   ```bash
   python3 preprocess/scripts/align_poses_to_3dgs.py \
       preprocess/output/images/<run_id> \
       preprocess/output/odometry/<run_id>/odometry.csv \
       preprocess/output/odometry/<run_id>/transforms.json
   ```
4. **Step 4 (Sparse Point Cloud for Initialization):**
   ```bash
   python3 preprocess/scripts/export_pcd_to_ply.py \
       preprocess/output/cloud_registered/<run_id>/scans.pcd \
       preprocess/output/cloud_registered/<run_id>/initial_points.ply
   ```
5. **Step 5 (Train 3DGS / 2DGS):**
   Train using `gsplat`, `gaussian-splatting`, or `nerfstudio` with the generated `transforms.json` and `initial_points.ply`.
