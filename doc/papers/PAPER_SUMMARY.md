# Paper Summary: Automated Weld Seam Detection and 3D Map Integration for Industrial Vessel Inspection Using Depth Cameras and 3D LiDAR

**Paper Title:** Automated Weld Seam Detection and 3D Map Integration for Industrial Vessel Inspection Using Depth Cameras and 3D LiDAR  
**Target Venue:** IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS 2026)  
**Authors:** Nontanut Chitsiriparat†, Run Janna†, Theerawath Phetpoon, Wasuthorn Ausrivong, Kanut Tarapongnivat, Worameth Nantareekurn, Suppachai Pewkliang, Poramate Manoonpong*  
**Affiliations:** Bio-inspired Robotics & Neural Engineering Lab, School of Information Science and Technology (IST), VISTEC; PTT Exploration and Production Public Company Limited (PTTEP)  
**Project Support:** HERO 2.1 Project (PTTEP) & National Science, Research and Innovation Fund (NSRF)  

---

## 1. Executive Summary & Problem Formulation

### 1.1 The Industrial Challenge
- **Pressure Vessel Inspection (Oil & Gas):** Regular non-destructive testing (NDT) of pressure vessels is strictly mandated (e.g., API 510) to prevent catastrophic failures.
- **Human Hazards:** Internal vessel inspection involves confined spaces, hazardous gases, toxic residues, and difficult access.
- **Limitations of Current Robotic Solutions:**
  - Most existing wall-climbing robots perform purely **image-based 2D visual tracking** or localized inspection in robot-centric frames.
  - They lack **globally registered spatial referencing** of weld seams. Defect logs cannot be reliably cross-referenced across periodic maintenance cycles or mapped directly onto plant digital twins / CAD models.
  - Surface curvature and arbitrary robot orientations cause standard thresholding / depth extraction methods to fail.

### 1.2 Proposed Core Innovation
An end-to-end perception and spatial mapping framework deployed onboard a magnetic-wheel wall-climbing robot that:
1. Deterministically detects weld seam centerlines and widths from local RGB-D frames without requiring pre-trained deep seam detectors.
2. Fuses local seam offsets with tightly-coupled LiDAR-Inertial Odometry (**FAST-LIO2**) into a globally consistent 3D seam trajectory.
3. Orders and smooths seam points via PCA and Savitzky–Golay filtering, generating a seam-consistent synthetic geometric overlay.
4. Identifies defect markers via fine-tuned YOLO, maps them to metric world coordinates, and clusters them using velocity-adaptive arc-length clustering.

---

## 2. Hardware & System Architecture

```
[Sensory Inputs]
├── RGB-D Camera (Intel RealSense D405) ──> Depth Profiles & RGB Frames
└── 3D LiDAR (Livox Mid-360) + Built-in IMU ──> FAST-LIO2 (LiDAR-Inertial Odometry)

[Computation & Embedded Control]
├── NVIDIA Jetson Orin NX (16GB, ROS 2 / ROS): All perception, SLAM, fusion onboard
└── ESP32-WROOM (Micro-ROS): Low-level motor control (swerve steering + driving)

[Locomotion System]
└── Magnetic-wheel climbing robot with active swerve steering modules and passive adaptive wings
```

- **Robot Platform:** HERO 2.1 platform. Magnetic wheels adhere to ferromagnetic steel vessel walls. Swerve steering allows omnidirectional trajectory adjustments while climbing.
- **Working Distance:** Short standoff distance $d_w \approx 0.08\text{--}0.10\text{ m}$ between the D405 camera and the steel surface.

---

## 3. Four-Stage Perception & Mapping Pipeline

### Module 1: Depth-Based Weld Seam Detection (Local Frame)
*Goal: Extract sub-millimeter lateral seam centerline displacement $\bar{p}^c_{\text{seam}}$ and physical width $\Delta w_{\text{seam}}$ from each noisy, tilted depth frame.*

1. **RANSAC Plane Estimation:**
   - Fits dominant surface plane $ax + by + cz + d = 0$ on the local depth point cloud ($0.01\text{ m}$ inlier threshold, 200 iterations). Normal $\vec{n} = [a, b, c]^\top$.
2. **Rodrigues Tilt Compensation:**
   - Rotates local point cloud via Rodrigues' rotation formula so the vessel normal aligns with the camera optical axis $\vec{k} = [0, 0, 1]^\top$:
     $$R_{\text{align}} = I + \sin\theta [u]_\times + (1 - \cos\theta) [u]_\times^2$$
   - Rotation is cached and updated every 5 frames to reduce compute.
3. **Row-wise Profile Extraction & Polynomial Detrending:**
   - Projects rotated cloud onto image plane, extracts 1D depth slices $Z_{h_i}(w)$ every 2 rows.
   - Fits and subtracts a 2nd-order polynomial $\hat{Z}_{\text{poly}}(w) = \hat{a}_2 w^2 + \hat{a}_1 w + \hat{a}_0$ to eliminate residual cylindrical wall curvature (sagitta $\approx 1\text{ mm}$ over the FOV).
4. **Adaptive Gaussian Matched Filtering:**
   - Convolves detrended profile with Gaussian kernel $G(\xi) = \exp(-\xi^2 / 2\sigma^2)$.
   - Sub-pixel peak localization via quadratic interpolation on the 3 discrete maximum samples:
     $$w_{\text{seam}} = -\frac{\beta_p}{2\alpha_p}$$
   - **Adaptive Kernel Update:** $\sigma_k$ smoothly adapts causal exponential smoothing based on the detected Full Width at Half Maximum ($\text{FWHM}$):
     $$\sigma_k = (1 - \alpha)\sigma_{k-1} + \alpha \frac{\text{FWHM}_k}{2.355}, \quad \alpha = 0.1, \; \sigma \in [3, 20]\text{ px}$$
5. **2D Line Fitting (RANSAC + TLS):**
   - Filters candidate center pixels using 2D RANSAC line fit, followed by Total Least Squares (TLS via SVD).

---

### Module 2: Coordinate Fusion & 3D Seam Path Reconstruction
*Goal: Transform per-frame 2D/3D seam detections into global coordinates without modifying the SLAM backend.*

- Rigid transform chaining:
  $$p_{\text{seam}}^W = R_b^W \left( R_c^b \, \bar{p}^c_{\text{seam}} + t_c^b \right) + t_b^W$$
  - $(R_c^b, t_c^b)$: Calibrated camera-to-body mechanical mounting.
  - $(R_b^W, t_b^W)$: Real-time 6-DOF robot pose from **FAST-LIO2**.
- Incremental sampling rules:
  - Pose updates accepted if translation $> 0.05\text{ m}$.
  - Samples spaced by $d_{\text{sample}} = 0.05\text{ m}$.
  - Displacements $> d_{\text{gap}} = 0.2\text{ m}$ start a new segment (avoids false interpolation across disconnected runs).

---

### Module 3: Seam-Consistent Synthetic Point Cloud Generation
*Goal: Ensure spatial monotonicity and generate a visual inspection layer for operators.*

- **PCA Ordering:** Computes first principal eigenvector $v_1$ of seam covariance matrix; sorts points along $\tau_i = (p_i - \bar{p})^\top v_1$.
- **Savitzky–Golay Trajectory Smoothing:** Window length $L=11$, polynomial order $p=3$ per coordinate axis.
- **Synthetic Cloud Generation:** Resamples path at $\Delta d = 2\text{ mm}$. Generates synthetic dense points:
  $$p_{\text{dense}} = p_{\text{int}} + \epsilon, \quad \epsilon \sim \mathcal{U}\left(-\frac{\Delta w_{\text{seam}}}{2}, \frac{\Delta w_{\text{seam}}}{2}\right)^3$$
  *(Note: This is a synthetic geometric overlay for visualization, NOT actual reconstructed surface geometry!)*

---

### Module 4: Target-Point (Defect) Detection & Localization
*Goal: Detect localized defects along the seam and accurately position them in the global coordinate frame.*

1. **YOLO Instance Segmentation:** Extracts bounding box centers $(u_c, v_c)$ on RGB stream for target markers (confidence $\ge 0.60$).
2. **Metric Projection:** Converts pixel offsets to camera metric offsets using horizontal FOV and working distance $d_w$, then transforms into world frame.
3. **Seam Snapping:** Snaps candidate points to nearest arc-length coordinate $s$ on the reconstructed seam via KD-tree query (rejects points beyond $d_{\text{snap}}$).
4. **Velocity-Adaptive Clustering:**
   - Merges multiple detections of the same defect across consecutive frames using dynamic threshold:
     $$d_{\text{merge}} = \min(d_{\text{base}} + \lambda \bar{v}, \, d_{\text{max}})$$
     with $d_{\text{base}} = 0.10\text{ m}$, $\lambda = 0.5\text{ s}$, $d_{\text{max}} = 0.30\text{ m}$, $n_{\text{min}} = 3$.
   - Prevents over/under-segmentation when robot motion speed varies.
5. **Confidence-Weighted Centroid:** Computes final metric defect coordinates:
   $$\hat{p}_k = \sum_{j=1}^{N_k} w_j p_j, \quad w_j = \frac{c_j}{\sum_l c_l}$$

---

## 4. Key Experimental Results & Metrics

| Metric / Scenario | Longitudinal Seam | Circumferential Seam | Global System Level |
|---|---|---|---|
| **Per-Frame Centerline MAE** | **0.76 mm** (P95: 1.66 mm) | **1.10 mm** (P95: 2.06 mm) | — |
| **Angular Error** | 1.61° | 0.90° | — |
| **F1 Score / Coverage** | 0.676 / 83.5% | 0.650 / 87.8% | — |
| **Global Seam Trajectory MAE** | — | — | **13.37 mm** (P95: 26.06 mm) |
| **Defect Localization MAE** | — | — | **2.60 cm** along seam |
| **Defect Ordering Consistency** | — | — | **96.7%** (30 cm GT spacing) |
| **Runtime / Frequency** | — | — | **4.6 – 4.8 Hz** (210–218 ms/frame) |

---

## 5. Critical Limitations Highlighted in the Paper

1. **No True 3D Surface Reconstruction of the Weld Bead:**
   - Module 3 only generates a *synthetic ribbon of points* based on estimated width $\Delta w_{\text{seam}}$ and centerline $p_{\text{int}}$.
   - It cannot capture actual 3D bead morphology: weld cap elevation, ripples, toe geometry, weld undercuts, micro-cracks, or pitting.
2. **RGB-D Sensor Artifacts on Curved Metallic Surfaces:**
   - Active IR stereo (RealSense D405) suffers from specular reflections, depth noise, edge dropouts, and multi-path scattering on polished/ground steel and oily coatings.
3. **1D Profile & Line Fitting Assumptions:**
   - The matched filter assumes a single smooth convex Gaussian peak. Real-world welds with double-bead passes, severe undercuts, or irregular grinding violate this 1D model.
4. **LiDAR Resolution Gap:**
   - Livox Mid-360 LiDAR provides centimeter-level global positioning, but cannot resolve millimeter or sub-millimeter surface features on the steel wall.
5. **Single-Pass Limitation:**
   - Multi-pass trajectory overlaps are not merged or co-registered; forward and return paths remain disconnected traces.
6. **Frame Rate:**
   - 4.8 Hz is adequate for manual teleoperation at slow speeds ($\sim 0.05\text{ m/s}$), but limits closed-loop high-speed automated tracking.
