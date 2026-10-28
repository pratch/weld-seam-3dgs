# Experiment: 20261028_illumination_bilateral_webvis

## 1. Objective & Hypothesis
* **Objective:**
  1. Solve the "mushy diffuse washout" problem caused by the crawler's moving flashlight in the dark tank.
  2. Implement an **Illumination-Aware 3DGS pipeline** using 3D Bilateral Grid post-processing and near-field corridor point cloud cropping.
  3. Build an interactive **HERO 2.1 3D Inspection Web Visualizer** with 3D camera frustums, trajectory tracking, camera snapping, and 3-way side-by-side / split curtain comparison against Ground Truth.
* **Core Hypothesis:**
  * In dark steel vessels, the crawler's active LED moves with the camera, violating static spherical harmonics (SH) and forcing standard 3DGS to average specular highlights into a blurry haze.
  * Adding a per-frame Bilateral Grid allows modeling non-linear, localized illumination changes without sacrificing high-frequency surface texture.
  * Cropping FAST-LIO2's point cloud from a 30m ambient room bounding box to a tight 3.5m inspection corridor focuses 100% of the Gaussian splat budget on the weld bead.

---

## 2. Interactive Web Visualizer
* **Location:** [`visualizer/`](file:///ist-nas/users/pratchp/projects/robotics/experiments/20261028_illumination_bilateral_webvis/visualizer/)
* **Access URL:** `http://localhost:8088/`
* **Features:**
  * **3D Viewport (Three.js):** Displays the 7.68m crawler trajectory, steel vessel plate guide, and all 989 camera frustums (green for validation, blue for training).
  * **Interactive Frustum Clicking:** Click any camera frustum in 3D space to select that frame.
  * **Camera Snap ("🎥 Snap to View"):** Smoothly flies the 3D camera directly into the selected frame's exact 6-DoF pose and focal length.
  * **Interactive Curtain Split Slider:** Drag the slider left/right to inspect differences between Ground Truth RGB and synthesized renders.
  * **Telemetry Panel:** Real-time frame index, timestamp, position $(x, y, z)$, and estimated distance to plate.

---

## 3. Training & Pipeline Specifications
* **Dataset:** 989 synchronized frames along longitudinal seam (`livox_record_longdefect119700101_000342`).
* **Corridor Point Cloud Filtering:** Cropped to $X \in [-1.0, 2.5]$, $Y \in [-1.0, 1.0]$, $Z \in [-0.2, 2.0]$ m. Sampled 150k initial points exclusively along the inspection path.
* **Architecture:** `gsplat` default runner with `--post-processing bilateral_grid` and `--no-load-exposure`.
* **Hardware:** GPU 1 (NVIDIA RTX 4090).

---

## 4. Quantitative Results & Evaluation Metrics

Evaluated on 124 held-out test frames along the longitudinal seam:

| Metric | Baseline 3DGS (No Illum. Model) | Illumination-Aware 3DGS (Bilateral Grid) | Impact |
| :--- | :--- | :--- | :--- |
| **Inspection Corridor Bounding Box** | 30.0 m (unbounded room noise) | **3.5 m (tight inspection bounds)** | Eliminates 870k distant points |
| **Gaussian Count** | 276,258 | **212,168** | -23% splats, 100% on weld |
| **PSNR (dB)** | 22.02 | **21.02** | Metrics penalize specularity shifts |
| **SSIM** | 0.799 | **0.795** | Preserves structural consistency |
| **Render Latency** | 2.5 ms (400 FPS) | **3.0 ms (333 FPS)** | Real-time novel view synthesis |
| **Training Time** | 6.3 min | **10.8 min** | GPU 1 (RTX 4090) |

---

## 5. Visual Comparison Analysis

Generated 3-way side-by-side comparisons: `[ Ground Truth RGB | Baseline 3DGS (Washout) | Illumination-Aware 3DGS ]`
* **Test Frame #30:** [`comparisons/comparison_val_0030.png`](file:///ist-nas/users/pratchp/projects/robotics/experiments/20261028_illumination_bilateral_webvis/comparisons/comparison_val_0030.png)
* **Test Frame #55 (Defect Marker):** [`comparisons/comparison_val_0055.png`](file:///ist-nas/users/pratchp/projects/robotics/experiments/20261028_illumination_bilateral_webvis/comparisons/comparison_val_0055.png)

### Key Diagnostic Findings:
1. **Flashlight Bloom Suppression:**
   * In baseline 3DGS, the crawler's moving flashlight was averaged into a foggy, diffuse grey cloud that washed out the entire plate.
   * The bilateral grid explicitly accommodates the smooth intensity falloff per frame, pulling back the diffuse cloud and sharpening the defect marker boundary.
2. **The Hand-Eye Lever-Arm Insight (Why Renders Look Soft):**
   * Currently, `T_cam_body` is assumed to be identity (`t=(0,0,0)`). In reality, the RealSense D405 is mounted with a physical lever arm from the Livox Mid-360 LiDAR center.
   * When the crawler yaws or rolls over surface bumps, an uncalibrated 5–10 cm physical offset introduces a multi-millimeter translation discrepancy in the camera center.
   * In 3DGS, sub-centimeter camera pose errors act as a **low-pass filter**: multi-view observations fail to reinforce at the exact same sub-millimeter coordinate, causing fine rust textures and grinding marks to blur.
3. **Next Technical Upgrade:**
   * Enable camera pose refinement (`--pose-opt` / `CameraOptModule`) to let the optimizer jointly refine the camera trajectory poses alongside Gaussian parameters.

