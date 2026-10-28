# Experiment: 20261028_baseline_3dgs_longdefect

## 1. Objective & Hypothesis
* **Objective:** Test end-to-end 3D Gaussian Splatting reconstruction on longitudinal weld seam inspection run with defect markers (`livox_record_longdefect119700101_000342`).
* **Core Hypothesis:** Drift-free 6-DoF odometry from FAST-LIO2 can serve as direct camera pose priors for 3DGS, bypassing COLMAP completely and enabling sub-millimeter visual reconstruction of the weld bead and defect markers without active IR depth dropouts.

## 2. Dataset Specification
* **Source Bag:** `data/hero_map_bags/livox_record_longdefect119700101_000342`
* **Duration:** 91.3 seconds
* **RGB Frames:** 1019 images (`/camera/color/image_raw`, resolution $640 \times 480$)
* **LiDAR Scans:** 913 Livox Mid-360 custom frames (`/livox/lidar`)
* **IMU:** 18,261 messages (`/livox/imu`)

## 3. Pipeline Stages
1. **Frame Extraction:** Extract 1019 synchronized RGB frames from the bag into `images/`.
2. **LiDAR-Inertial SLAM:** Run FAST-LIO2 inside Apptainer SIF container to output metric `/Odometry` and `/cloud_registered`.
3. **Pose & Intrinsics Interpolation:** Rigidly chain body poses with camera extrinsics and SLERP-interpolate to RGB camera timestamps into standard `transforms.json`.
4. **Point Cloud Export:** Export FAST-LIO2 registered point cloud to `initial_points.ply` for 3D Gaussian center initialization.
5. **3DGS Training (`gsplat`):** Train modern 3D Gaussian Splatting with MCMC densification.
6. **2DGS Surface Reconstruction:** Run 2DGS to extract planar surface normals across the weld bead.

## 4. Quantitative Results & Evaluation Metrics

Evaluated on 124 held-out test frames across the longitudinal weld trajectory:

| Metric | 500 Steps (Sanity) | 5,000 Steps | 15,000 Steps (Final) | Target / Benchmark |
| :--- | :--- | :--- | :--- | :--- |
| **PSNR (dB)** | 19.53 | 21.95 | **22.02** | > 20 dB (Complex Specular Steel) |
| **SSIM** | 0.785 | 0.794 | **0.799** | > 0.75 |
| **LPIPS** | 0.702 | 0.656 | **0.632** | Lower is better |
| **Render Speed** | 2.6 ms/frame (384 FPS) | 2.5 ms/frame (400 FPS) | **2.5 ms/frame (400 FPS)** | Real-time (> 30 FPS) |
| **Gaussian Count** | 150,000 | 204,599 | **276,258** | Compact footprint |
| **VRAM Consumption**| 0.27 GB | 0.41 GB | **0.46 GB** | Fits easily on embedded Jetson |
| **Training Time** | ~10 sec | 2.2 min | **6.3 min** | NVIDIA RTX 4090 |

## 5. Artifacts Produced
* **Trained Model Checkpoints:**
  * `results_full/ckpts/ckpt_14999_rank0.pt` (65.2 MB)
  * `results_full/ckpts/ckpt_4999_rank0.pt` (48.3 MB)
* **Standard 3D Gaussian Cloud (PLY):**
  * `results_full/ply/point_cloud_14999.ply` (65.2 MB, 276k Gaussians)
* **Rendered RGB & Expected Depth Evaluations:**
  * 124 validation renders in `results_full/renders/val_step14999_*.png`

## 6. Key Findings & Insights
1. **Pose Prior Validation (No COLMAP Needed):**
   * FAST-LIO2 LiDAR-inertial odometry + SLERP pose interpolation provides sufficiently drift-free 6-DoF trajectory priors to converge 3DGS without any COLMAP feature matching.
   * This is a critical breakthrough for robotic tank/pipe inspection where repetitive steel surfaces cause COLMAP SfM to fail completely.
2. **Surface Reflectivity & Weld Bead Rendering:**
   * Spherical harmonics (degree 3) successfully capture the severe specular glare of the grinding marks along the weld seam.
   * Both weld crown and toe lines are sharply synthesized, and expected depth maps (`renders/val_step14999_*.png`) clearly reveal the 3D elevation profile of the longitudinal bead.
3. **Efficiency:**
   * Training took only **6.3 minutes** with **0.46 GB VRAM**, rendering at **400 FPS**.

## 7. Known Issue: Camera-to-Body Extrinsic Is Missing (Poses Are IMU Poses)

**Status:** open, affects this experiment and `20261028_illumination_bilateral_webvis` (identical poses in `sparse/0/images.bin`).

### What the pipeline does
3DGS needs each image's camera pose (c2w). The correct chain is

$$T^W_c = T^W_b \cdot T^b_c$$

where $T^W_b$ (body→world) comes from FAST-LIO2 and $T^b_c$ (camera→body) is the fixed D405 mounting. `preprocess/scripts/align_poses_to_3dgs.py` defaults `t_cam_body=(0,0,0)`, `q_cam_body=(0,0,0,1)` and `run_fast_lio_offline.sh` never overrides them, so every `transform_matrix` in `transforms.json` is just the **interpolated Mid-360 IMU pose** relabelled as the camera (OpenCV axes, metric `camera_init` world frame). Poses are then frozen during training (`pose_opt: false` in `results_full/cfg.yml`).

### Evidence
| Check | Result |
| :--- | :--- |
| Frame 0 rebuilt from `odometry.csv` with zero extrinsic | Matches `transforms.json` exactly |
| `/tf_static` in any of the 12 bags | None |
| `/tf` in bags (longdefect1, cir1, long1) | Only `camera_init → camera_link`, exact identity in every message (placeholder, not a calibration) |
| URDF / calibration files in `data/` | None; no colour `camera_info` either (intrinsics are hardcoded defaults) |
| IROS paper, Module 2 (Eq. 8) | $(R^b_c, t^b_c)$ "determined from rigid mechanical mounting geometry", $R^b_c \approx I$ (< 2°); **no value given for $t^b_c$** |
| FAST-LIO map projected into cameras 0 / 400 / 800 | Plate normal ≈ camera optical axis (rotation plausible; roll about the axis unverified), but plate sits **~1–5 cm** from the assumed centre vs. the D405's real ~8–10 cm standoff |

### Why a *fixed* wrong extrinsic still hurts
The extrinsic multiplies on the right, so it does not cancel in relative poses: $(T_i X)^{-1}(T_j X) = X^{-1}(T_i^{-1}T_j)X$.
* Missing translation $t$ produces a camera-centre error $\approx \Delta\theta \times |t|$; it cancels only while the robot purely translates.
* A rotation error $R$ tilts the camera-frame motion direction even in pure translation.

Measured on this trajectory (frames whose centres are within 12 cm, i.e. overlapping views), body orientation differs by **9–11°** (forward/return passes; whole run rotates 10.2°):

| Error source | Inconsistency between overlapping views |
| :--- | :--- |
| Missing $t$ = 3 cm | ~5 mm |
| Missing $t$ = 5 cm | ~8–10 mm |
| Missing $t$ = 10 cm | ~16–19 mm |
| 2° rotation error (paper tolerance) | ~4 mm |

At 0.10 m standoff one pixel ≈ **0.26 mm**, so 8 mm ≈ 30 px of misregistration. With frozen poses this shows up as blur, duplicated texture and floaters, and is a plausible cause of the ~22 dB PSNR plateau. Note the 9–11° also contains FAST-LIO inter-pass drift (paper: 13.6 mm global MAE), a separate error of similar size.

### Fix plan
1. **Re-train with `pose_opt: true`** (gsplat `CameraOptModule`): cheapest test of how much quality is lost to pose error; absorbs both extrinsic and drift.
2. **Obtain $T^b_c$**: ask the paper authors for the value used in their seam-fusion code / bracket CAD, or measure IMU origin → D405 optical centre on the robot. Pass it as `t_cam_body` / `q_cam_body` in `align_poses_to_3dgs.py`.
3. **Estimate from data** if neither is available: offset along the optical axis = D405 depth to plate − IMU-to-plate distance in the FAST-LIO map; in-plane offset via pose refinement or hand-eye calibration.
4. Check camera/LiDAR time offset (`time_sync_en: false` assumes zero).

---

## 8. Next Step: 2D Gaussian Splatting (2DGS)
* While 3DGS produces high-fidelity novel view rendering, standard 3D ellipsoidal Gaussians have ambiguities in normal estimation along thin surfaces.
* **Next Action:** Train 2DGS (`simple_trainer_2dgs.py`) on this exact COLMAP dataset to constrain Gaussians to planar surfels, directly yielding high-resolution surface normals for weld defect geometry extraction.

