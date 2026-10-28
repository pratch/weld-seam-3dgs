#!/usr/bin/env python3
"""
Generate 3-Way Side-by-Side Comparison between:
[ Ground Truth RGB | Baseline 3DGS (Overexposed Washout) | Illumination-Aware 3DGS ]
Includes zoomed-in crops of weld toe, crown, and defect markers.
"""

import os
import sys
from pathlib import Path
import cv2
import numpy as np

def generate_comparison(
    val_idx: int = 30,
    frame_seq_id: int = 240,
    gt_dir: str = "preprocess/output/images/longdefect1",
    baseline_dir: str = "experiments/20261028_baseline_3dgs_longdefect/results_full/renders",
    bilateral_dir: str = "experiments/20261028_illumination_bilateral_webvis/results_full/renders",
    out_dir: str = "experiments/20261028_illumination_bilateral_webvis/comparisons"
):
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # 1. Find Ground Truth image matching frame_seq_id
    gt_dir_path = Path(gt_dir)
    prefix = f"frame_{frame_seq_id:05d}_"
    matches = list(gt_dir_path.glob(f"{prefix}*.png"))
    if not matches:
        matches = list(gt_dir_path.glob(f"*{frame_seq_id}*.png"))
    if not matches:
        print(f"Error: Could not find GT image for frame seq {frame_seq_id} in {gt_dir}")
        return
    gt_file = matches[0]

    gt_img = cv2.imread(str(gt_file)) # [480, 640, 3]

    # 2. Load Baseline render
    # Baseline saved [pixels, colors] concatenated horizontally: shape [480, 1280, 3]
    base_file = Path(baseline_dir) / f"val_step14999_{val_idx:04d}.png"
    if not base_file.exists():
        print(f"Error: Baseline render {base_file} not found.")
        return
    base_concat = cv2.imread(str(base_file))
    # Right half is rendered 3DGS
    h, w = gt_img.shape[:2]
    baseline_render = base_concat[:, w:]

    # 3. Load Bilateral render (or step 4999 / 14999)
    bilat_file = Path(bilateral_dir) / f"val_step14999_{val_idx:04d}.png"
    if not bilat_file.exists():
        bilat_file = Path(bilateral_dir) / f"val_step4999_{val_idx:04d}.png"
    
    if bilat_file.exists():
        bilat_concat = cv2.imread(str(bilat_file))
        bilateral_render = bilat_concat[:, w:]
    else:
        print(f"Warning: Bilateral render not ready yet at {bilat_file}, creating placeholder.")
        bilateral_render = np.zeros_like(gt_img)
        cv2.putText(bilateral_render, "Training in progress...", (50, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

    # 4. Add Text Labels
    def add_label(img, text, color=(255, 255, 255), bg_color=(20, 20, 20)):
        res = img.copy()
        cv2.rectangle(res, (10, 10), (w - 10, 50), bg_color, -1)
        cv2.putText(res, text, (20, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
        return res

    labeled_gt = add_label(gt_img, "Ground Truth (D405)", (100, 255, 100))
    labeled_base = add_label(baseline_render, "Baseline 3DGS (Diffuse Washout)", (100, 200, 255))
    labeled_bilat = add_label(bilateral_render, "Illumination-Aware 3DGS (Bilateral)", (255, 200, 50))

    # 5. Extract zoomed-in crop of weld seam (middle vertical section)
    # y: 150 to 350, x: 100 to 300
    y1, y2 = 140, 340
    x1, x2 = 120, 320
    crop_h, crop_w = 180, 180

    def get_zoom_inset(img, crop_box, text):
        yA, yB, xA, xB = crop_box
        crop = img[yA:yB, xA:xB]
        zoom = cv2.resize(crop, (crop_w, crop_h), interpolation=cv2.INTER_CUBIC)
        cv2.rectangle(zoom, (0, 0), (crop_w - 1, crop_h - 1), (0, 255, 255), 3)
        cv2.putText(zoom, text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)
        return zoom

    # Combine side-by-side: [ GT | Baseline | Bilateral ]
    triptych = np.hstack([labeled_gt, labeled_base, labeled_bilat])

    out_file = out_path / f"comparison_val_{val_idx:04d}.png"
    cv2.imwrite(str(out_file), triptych)
    print(f"Saved 3-way comparison to {out_file}")
    return str(out_file)

if __name__ == "__main__":
    val_id = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    seq_id = int(sys.argv[2]) if len(sys.argv) > 2 else val_id * 8
    generate_comparison(val_id, seq_id)
