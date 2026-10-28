# 3D Gaussian Splatting (3DGS) for Industrial Weld Seam & Defect Reconstruction
## Bridging the Gap: From Synthetic Annotation Overlays to True Sub-Millimeter Digital Twins

This document is prepared for your meeting with **Run Janna** and his advisor (**Prof. Poramate Manoonpong**) to explain why the current system struggles with thin/line structures and how **3D Gaussian Splatting (3DGS)** offers an ideal complementary research direction.

---

## 1. Why the Paper's Current Method Fails on Thin / Line Structures

In the paper (*Chitsiriparat, Janna et al., IROS 2026*), the authors developed a pragmatic perception pipeline for an industrial crawling robot. However, several architectural design choices fundamentally limit its ability to capture fine, thin, or high-frequency surface features:

### A. The Method Does NOT Actually Reconstruct the 3D Seam Surface
- In Section III-C (Module 3), the authors explicitly state:
  $$\text{"...not a direct surface reconstruction. The resulting representation serves as a visual annotation layer over the global map—a synthetic geometric overlay parameterized by the estimated seam width."}$$
- In code and formula:
  $$p_{\text{dense}} = p_{\text{int}} + \epsilon, \quad \epsilon \sim \mathcal{U}\left(-\frac{\Delta w_{\text{seam}}}{2}, \frac{\Delta w_{\text{seam}}}{2}\right)^3$$
- The system merely places a synthetic ribbon of random points around a 1D spline curve. It has **no knowledge of actual 3D bead topology** (weld toe angles, bead crown height, ripple frequency, or bead root profile).

### B. 1D Signal Processing Acts as a Low-Pass Filter
- Module 1 slices the depth map into 1D horizontal cross-sections, subtracts a second-order polynomial, and applies a **Gaussian matched filter** ($G(\xi) = \exp(-\xi^2 / 2\sigma^2)$) with $\sigma \in [3, 20]$ pixels.
- This assumes the weld is a single, broad, smooth convex Gaussian peak.
- **Why this fails on thin/line structures:**
  1. **Hairline cracks & micro-flaws:** Cracks are narrow, high-frequency negative depressions (sub-millimeter width). The Gaussian convolution and polynomial detrending treat them as high-frequency noise and smooth them away completely.
  2. **Weld toes & undercuts:** The junction between the weld bead and the base plate (the toe) is a sharp, thin crease line. A 1D smooth Gaussian cannot localize sharp discontinuities.
  3. **Multi-pass & complex bead profiles:** If a weld consists of overlapping weld beads or has an irregular crown, the 1D peak detector collapses the entire structure into a single erroneous centroid.

### C. Active Stereo (RealSense D405) Fails on Shiny Curved Metal
- The Intel RealSense D405 uses active infrared (IR) stereo projection.
- Steel pressure vessel walls and freshly ground weld beads are **highly specular (reflective)** and anisotropic.
- Active IR patterns scatter and create severe multi-path reflections, resulting in:
  - **Depth dropouts / black holes** (no stereo disparity match).
  - **Flying pixels / edge fattening** along thin metallic ridges and seams.
  - In the paper, Table I reports per-frame coverage of only 83–87%, meaning 13–17% of frames have degraded or missing seam detections.

### D. 3D LiDAR (Livox Mid-360) is Too Coarse for Local Surface Details
- While the Livox Mid-360 is great for FAST-LIO2 robot localization, its angular resolution and spot size (~cm level) cannot resolve millimeter-scale weld geometries or thin defects.

---

## 2. Why 3D Gaussian Splatting (3DGS) is the Solution

3D Gaussian Splatting (Kerbl et al., SIGGRAPH 2023) and its surface-aligned extensions (2DGS, SuGaR, GOF) provide specific mathematical properties that solve these exact failure modes:

```
+-------------------------------------------------------------------------+
|                  Why 3DGS Solves the Limitations                         |
+-------------------------------------------------------------------------+
|  1. Anisotropic Gaussians   -->  Naturally stretch into ultra-thin      |
|                                  lines and flat surfels (cracks/toes)   |
|  2. Spherical Harmonics     -->  Accurately models specular metallic   |
|                                  highlights and reflections             |
|  3. Differentiable Loss     -->  Optimized via high-res RGB pixels      |
|                                  (sub-millimeter texture details)       |
|  4. Metrically Anchored     -->  Uses FAST-LIO2 poses directly;         |
|                                  NO COLMAP SfM failures in dark tanks!  |
+-------------------------------------------------------------------------+
```

### 1. Anisotropic Geometry Naturally Represents Thin Lines
- Each 3D Gaussian is defined by a 3D covariance matrix $\Sigma = R S S^\top R^\top$, where $S = \text{diag}(s_x, s_y, s_z)$ contains 3 independent scale factors.
- Unlike voxels (isotropic cubes) or raw point clouds, Gaussians can have extreme aspect ratios (e.g., $s_x \gg s_y, s_z$).
- They can represent **thin 1D lines** (weld edges, crack trajectories, seam boundaries) and **thin 2D surfaces** without discretization errors or edge fattening.

### 2. Handling Specular Metal via View-Dependent Radiance (Spherical Harmonics)
- Standard multi-view stereo algorithms assume surfaces are Lambertian (diffuse matte). They fail on metallic weld seams because reflected light shifts with the viewing angle.
- 3DGS represents color using spherical harmonics (SH) coefficients per Gaussian:
  $$C(v) = \sum_{l=0}^{k} \sum_{m=-l}^{l} c_l^m Y_l^m(v)$$
- As the robot crawls along the seam, 3DGS models how the metallic highlight moves across the weld crown, allowing accurate reconstruction of the underlying geometry rather than getting confused by specular glare.

### 3. Differentiable Photometric Optimization
- 3DGS renders images via tile-based rasterization and optimizes Gaussian positions, scales, rotations, and opacities directly against high-resolution RGB frames ($1280 \times 720$) using:
  $$\mathcal{L} = (1 - \lambda)\mathcal{L}_1(I_{\text{rendered}}, I_{\text{gt}}) + \lambda \mathcal{L}_{\text{D-SSIM}}(I_{\text{rendered}}, I_{\text{gt}})$$
- This extracts sub-millimeter visual cues that active IR depth sensors completely miss.

---

## 3. The Killer Collaboration Angle: FAST-LIO2 + 3DGS (No COLMAP Needed!)

Standard 3DGS has a major bottleneck: it depends on **COLMAP Structure-from-Motion (SfM)** to estimate camera poses and an initial sparse point cloud.
- In industrial tanks, surfaces have repetitive textures and dim lighting. **COLMAP frequently fails, yields scale ambiguity, or produces corrupted camera trajectories.**

### The Breakthrough Synergy:
Run's pipeline **already solves the hardest problem for 3DGS**:
1. **Accurate Metric Poses:** FAST-LIO2 provides drift-free, metrically accurate 6-DoF robot body poses $(R_b^W, t_b^W)$ in real time.
2. **Rigid Hand-Eye Extrinsics:** The camera-to-body transform $(R_c^b, t_c^b)$ is rigidly fixed and calibrated.
3. **Sparse Metric Initialization:** FAST-LIO2's LiDAR map and initial D405 depth points provide the initial 3D Gaussian centers with true metric scale!

```
[HERO 2.1 Robot Crawling]
        │
        ├── Livox Mid-360 LiDAR + IMU  ──>  FAST-LIO2 Odometry  ──>  Accurate 6-DoF Metric Poses
        │                                                                  │
        └── RealSense D405 (RGB Stream) ───────────────────────────────────┼──>  Direct 3DGS Optimization
                                                                           │     (Sub-millimeter weld bead
                                                                           v      & defect reconstruction)
                                                              [Dense Metric Digital Twin]
```

By passing FAST-LIO2 poses directly into 3DGS, we bypass COLMAP entirely. We get an automated, metric, sub-millimeter 3D reconstruction of the weld seam!

---

## 4. Proposed Collaborative Roadmap

| Phase | Objective | Method / Technology | Expected Deliverable |
|---|---|---|---|
| **Phase 1: Dataset & Data Preparation** | Extract synchronized RGB frames and FAST-LIO2 poses from Run's recorded ROS bags | `rosbags` / custom extraction script; format into standard 3DGS camera format (`transforms.json` or COLMAP pose format) | Benchmark inspection dataset with ground truth |
| **Phase 2: Pose-Conditioned 3DGS Training** | Train 3DGS / 2DGS on weld seam sequences using FAST-LIO2 poses | `gsplat` / `gaussian-splatting` with LiDAR pose initialization | High-fidelity photorealistic novel-view synthesis of weld seams |
| **Phase 3: Thin Structure & Defect Metric Extraction** | Reconstruct surface normals and extract true weld bead profile (reinforcement height, toe angle, cracks) | Surface Gaussian Splatting (2DGS / SuGaR / PGSR) for mesh & normal extraction | Automated measurement of weld dimensions compliant with API 510 |
| **Phase 4: Real-time / Onboard Integration** | Streamline 3DGS model for online or edge incremental reconstruction on Jetson Orin NX | Compact 3DGS / Fast Gaussian Splatting | Onboard digital twin generation for HERO 2.1 |

---

## 5. Talking Points & Agenda for Tomorrow's Meeting

### Opening & Acknowledgments
1. Congratulate Run and his advisor on the HERO 2.1 robot and the IROS paper submission.
2. Emphasize that the integration of deterministic depth processing with FAST-LIO2 provides a solid, practical foundation for spatial referencing.

### Presenting the 3DGS Opportunity
3. **Point out the core observation:**
   *"The paper's Module 3 produces a synthetic geometric overlay (a uniform random distribution around a 1D centerline) rather than true 3D surface geometry. This works for visualizing approximate seam paths, but cannot perform true NDT flaw sizing (undercuts, toe cracks, weld bead geometry)."*
4. **Explain how 3DGS solves thin structures & specularity:**
   *"3DGS represents geometry using anisotropic Gaussians and spherical harmonics. It can represent needle-thin cracks, sharp weld toes, and specular reflections on curved steel without depth dropout."*
5. **Highlight the win-win collaboration:**
   *"Usually, 3DGS fails in industrial environments because COLMAP SfM cannot handle repetitive metallic textures. But Run already has FAST-LIO2 providing rock-solid metric poses and LiDAR points. We can plug your FAST-LIO2 poses directly into our 3DGS pipeline to achieve true metric, sub-millimeter digital twin reconstruction!"*
6. **Next concrete steps:**
   - Run shares the raw ROS bag files containing synchronized D405 RGB frames and FAST-LIO2 odometry (`/Odometry` or `/tf`).
   - Run a test 3DGS reconstruction on one longitudinal and one circumferential seam run to demonstrate reconstructed weld details.
