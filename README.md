# weld-seam-3dgs

Photorealistic, metric 3D reconstruction of weld seams on industrial pressure vessels, captured by the **HERO 2.1** magnetic-wheel climbing robot (VISTEC × PTTEP).

The robot carries an **Intel RealSense D405** (RGB-D at 8–10 cm standoff) and a **Livox Mid-360** LiDAR + IMU. Instead of running COLMAP, which fails on shiny, repetitive steel, we take camera poses from **FAST-LIO2** LiDAR-inertial odometry and initialize Gaussians from its registered point cloud, then train **3D Gaussian Splatting** (gsplat) to get an inspectable digital twin of the seam.

```
ROS 2 bag ──► extract RGB frames ──────────────┐
          └─► FAST-LIO2 (Apptainer) ─► poses ──┼─► transforms.json ─► COLMAP sparse/0 ─► gsplat ─► PLY ─► web visualizer
                                     └► registered cloud ─► init points ┘
```

## Folder structure

| Path | Contents |
| :--- | :--- |
| `data/` | 12 raw ROS 2 bags (`hero_map_bags/`), videos, download links. **Not in git** (31 GB). |
| `doc/` | Onboarding guide, 3DGS proposal, IROS 2026 paper + summary |
| `preprocess/` | FAST-LIO2 config, container recipes, pose alignment / COLMAP / PLY export scripts. `output/` and `fast_lio2.sif` not in git. |
| `experiments/<YYYYMMDD>_<name>/` | One folder per run: README (objective, command, metrics, findings) + scripts. Results/checkpoints not in git. |
| `visualizer/` | Three.js + GaussianSplats3D inspection viewer (trajectory, frustums, snap-to-camera, GT vs render slider, WASD). `ply_to_splat.py` converts trained PLYs to metric-frame `.splat`. |
| `inspect_bag.py`, `extract_bag_images.py`, `download_hero_map.py` | Root utilities for bag inspection, frame extraction, dataset download |

See [`CLAUDE.md`](CLAUDE.md) for the full step-by-step processing workflow and experiment protocol.

## Progress

- [x] Downloaded all 12 bags (long / longdefect / cir / cirdefect × 3)
- [x] FAST-LIO2 offline pipeline in Apptainer; processed `longdefect1` (888 poses, 1.32 M-point map)
- [x] Baseline 3DGS on `longdefect1`: **22.02 dB PSNR / 0.799 SSIM**, 276k Gaussians ([README](experiments/20261028_baseline_3dgs_longdefect/README.md))
- [x] Illumination-aware 3DGS (bilateral grid + corridor crop): 21.02 dB / 0.795 SSIM, 212k Gaussians ([README](experiments/20261028_illumination_bilateral_webvis/README.md))
- [x] Web visualizer: splats rendering in the metric FAST-LIO frame, aligned with camera poses

## TODO

**Pose accuracy (likely the main quality bottleneck)**
- [ ] **Camera-to-body extrinsic is missing:** poses are currently raw IMU poses (identity extrinsic). Not in any bag, and the paper gives no translation value. Causes ~5–10 mm inconsistency between overlapping views. Details and fix plan: [baseline README §7](experiments/20261028_baseline_3dgs_longdefect/README.md#7-known-issue-camera-to-body-extrinsic-is-missing-poses-are-imu-poses)
- [ ] Re-train with `pose_opt: true` to measure how much quality pose error costs
- [ ] Get $T^b_c$ from the paper authors / bracket CAD, or measure it on the robot
- [ ] Verify camera ↔ LiDAR time offset (`time_sync_en: false`)

**Pipeline**
- [ ] FAST-LIO segfaults on shutdown, so `scans.pcd` is never written; docs still reference it (`cloud_registered.ply` is used instead)
- [ ] Colour-camera intrinsics are hardcoded (bags only carry depth `camera_info`)
- [ ] Process the remaining 11 bags, especially circumferential seams (more rotation → larger extrinsic error)
- [ ] 2DGS / surface extraction for weld geometry (normals, crown height, toe angle)

**Visualizer**
- [ ] Serve `.ply`/`.ksplat` with spherical harmonics (`.splat` keeps base colour only)
- [ ] Replace hardcoded PSNR/SSIM, latency and plate distance with real values
- [ ] Clean floaters (e.g. in SuperSplat) for paper figures
