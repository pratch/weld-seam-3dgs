# Experiments Directory

This folder contains day-by-day experiment records, configurations, scripts, and evaluation results.

## Folder Naming Format

```
experiments/<YYYYMMDD>_<experiment_name>/
```

*Example:* `experiments/20261028_baseline_3dgs_longdefect1/`

---

## Required Contents for Every Experiment

Each experiment subfolder must contain a `README.md` documenting:

1. **Objective & Hypothesis:** Clear statement of what is being evaluated or changed.
2. **Dataset / Bag:** Exact bag path (e.g. `data/hero_map_bags/livox_record_longdefect119700101_000342`) and frame indices/timestamps used.
3. **Execution Command:** Reproducible shell command(s) used to launch preprocessing, training, and rendering.
4. **Configuration / Hyperparameters:** Key parameter changes (iterations, learning rate, resolution, loss weights).
5. **Results & Metrics:**
   - Quantitative: PSNR, SSIM, LPIPS, training duration, memory consumption.
   - Qualitative: Screenshots of reconstructed weld bead, surface normals, or defect visibility.
6. **Key Findings & Next Steps:** Takeaways and proposed follow-up experiments.
