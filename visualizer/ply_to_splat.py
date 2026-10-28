"""Convert a gsplat-trained PLY into a .splat file in the metric FAST-LIO2 world frame.

gsplat's Parser (normalize_world_space=True) trains in a re-centred, PCA-rotated and
~2x rescaled frame, but the visualizer's cameras (scene_data.json) are raw FAST-LIO2
poses. This recomputes gsplat's normalization transform from the experiment's
sparse/0 COLMAP files and applies its inverse to every Gaussian.

Usage (from project root):
    python3 visualizer/ply_to_splat.py \
        experiments/20261028_illumination_bilateral_webvis/results_full/ply/point_cloud_14999.ply \
        experiments/20261028_illumination_bilateral_webvis/sparse/0 \
        visualizer/model.splat
"""
import argparse
import struct
import sys

import numpy as np

SH_C0 = 0.28209479177387814


def rotmat2qvec(R):
    w = np.sqrt(max(0.0, 1 + R[0, 0] + R[1, 1] + R[2, 2])) / 2
    x = np.copysign(np.sqrt(max(0.0, 1 + R[0, 0] - R[1, 1] - R[2, 2])) / 2, R[2, 1] - R[1, 2])
    y = np.copysign(np.sqrt(max(0.0, 1 - R[0, 0] + R[1, 1] - R[2, 2])) / 2, R[0, 2] - R[2, 0])
    z = np.copysign(np.sqrt(max(0.0, 1 - R[0, 0] - R[1, 1] + R[2, 2])) / 2, R[1, 0] - R[0, 1])
    return np.array([w, x, y, z])


def quat_mul(a, b):
    aw, ax, ay, az = np.moveaxis(a, -1, 0)
    bw, bx, by, bz = np.moveaxis(b, -1, 0)
    return np.stack([aw * bw - ax * bx - ay * by - az * bz,
                     aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw], -1)


def qvec2rotmat(q):
    w, x, y, z = q
    return np.array([
        [1 - 2 * y * y - 2 * z * z, 2 * x * y - 2 * w * z, 2 * x * z + 2 * w * y],
        [2 * x * y + 2 * w * z, 1 - 2 * x * x - 2 * z * z, 2 * y * z - 2 * w * x],
        [2 * x * z - 2 * w * y, 2 * y * z + 2 * w * x, 1 - 2 * x * x - 2 * y * y],
    ])


def read_colmap_c2w(path):
    c2ws = {}
    with open(path, 'rb') as f:
        n, = struct.unpack('<Q', f.read(8))
        for _ in range(n):
            _, *qt, _ = struct.unpack('<i7di', f.read(64))
            name = b''
            while (c := f.read(1)) != b'\0':
                name += c
            num_pts2d, = struct.unpack('<Q', f.read(8))
            f.read(24 * num_pts2d)
            w2c = np.eye(4)
            w2c[:3, :3] = qvec2rotmat(qt[:4])
            w2c[:3, 3] = qt[4:]
            c2ws[name.decode()] = np.linalg.inv(w2c)
    return np.stack([c2ws[k] for k in sorted(c2ws)])


def read_colmap_points(path):
    pts = []
    with open(path, 'rb') as f:
        n, = struct.unpack('<Q', f.read(8))
        for _ in range(n):
            _, x, y, z, _, _, _, _, track_len = struct.unpack('<Q3d3BdQ', f.read(51))
            f.read(8 * track_len)
            pts.append((x, y, z))
    return np.array(pts)


def gsplat_normalization(sparse_dir, gsplat_root):
    """Replicates gsplat examples/datasets/colmap.py Parser normalization (T3 @ T2 @ T1)."""
    sys.path.insert(0, f'{gsplat_root}/examples/datasets')
    from normalize import align_principal_axes, similarity_from_cameras, transform_cameras, transform_points

    c2w = read_colmap_c2w(f'{sparse_dir}/images.bin')
    points = read_colmap_points(f'{sparse_dir}/points3D.bin')
    T1 = similarity_from_cameras(c2w)
    c2w = transform_cameras(T1, c2w)
    points = transform_points(T1, points)
    T2 = align_principal_axes(points)
    points = transform_points(T2, points)
    T = T2 @ T1
    if np.median(points[:, 2]) > np.mean(points[:, 2]):
        T = np.diag([1.0, -1.0, -1.0, 1.0]) @ T
    return T


def read_gsplat_ply(path):
    with open(path, 'rb') as f:
        props = []
        while (line := f.readline().decode().strip()) != 'end_header':
            tok = line.split()
            if tok[0] == 'element':
                count = int(tok[2])
            elif tok[0] == 'property':
                props.append(tok[2])
        data = np.fromfile(f, dtype=np.float32, count=count * len(props)).reshape(count, len(props))
    return {name: data[:, i] for i, name in enumerate(props)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('ply')
    ap.add_argument('sparse_dir', help='COLMAP sparse/0 dir the model was trained from')
    ap.add_argument('out')
    ap.add_argument('--gsplat-root', default='/ist-nas/users/pratchp/projects/gsplat')
    args = ap.parse_args()

    v = read_gsplat_ply(args.ply)
    T_inv = np.linalg.inv(gsplat_normalization(args.sparse_dir, args.gsplat_root))
    s = np.cbrt(np.linalg.det(T_inv[:3, :3]))
    R = T_inv[:3, :3] / s

    means = np.stack([v['x'], v['y'], v['z']], 1) @ T_inv[:3, :3].T + T_inv[:3, 3]
    scales = np.exp(np.stack([v['scale_0'], v['scale_1'], v['scale_2']], 1)) * s
    quats_wxyz = np.stack([v['rot_0'], v['rot_1'], v['rot_2'], v['rot_3']], 1)
    quats_wxyz = quat_mul(rotmat2qvec(R)[None], quats_wxyz / np.linalg.norm(quats_wxyz, axis=1, keepdims=True))
    rgb = 0.5 + SH_C0 * np.stack([v['f_dc_0'], v['f_dc_1'], v['f_dc_2']], 1)
    alpha = 1.0 / (1.0 + np.exp(-v['opacity']))

    order = np.argsort(-scales.prod(1) * alpha)
    out = np.zeros(len(order), dtype=[('pos', '<f4', 3), ('scale', '<f4', 3), ('rgba', 'u1', 4), ('rot', 'u1', 4)])
    out['pos'] = means[order]
    out['scale'] = scales[order]
    out['rgba'] = np.clip(np.concatenate([rgb, alpha[:, None]], 1)[order] * 255, 0, 255)
    out['rot'] = np.clip(quats_wxyz[order] * 128 + 128, 0, 255)
    out.tofile(args.out)
    print(f'Wrote {len(out)} splats to {args.out} (metric scale factor {s:.4f})')


if __name__ == '__main__':
    main()
