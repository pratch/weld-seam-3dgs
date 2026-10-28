import json
import numpy as np

with open('visualizer/scene_data.json', 'r') as f:
    data = json.load(f)

intrinsics = data['intrinsics']
frames = data['frames']

cameras_out = []
for i, fr in enumerate(frames):
    c2w = np.array(fr['c2w'])
    # Camera center in world space
    pos = c2w[:3, 3].tolist()
    # Rotation matrix
    rot = c2w[:3, :3].tolist()
    
    cameras_out.append({
        "id": i,
        "img_name": fr['file_name'],
        "width": intrinsics['w'],
        "height": intrinsics['h'],
        "position": pos,
        "rotation": rot,
        "fx": float(intrinsics['fx']),
        "fy": float(intrinsics['fy']),
        "is_val": fr.get('is_val', False)
    })

with open('visualizer/cameras.json', 'w') as f:
    json.dump(cameras_out, f, indent=2)

print(f"Exported {len(cameras_out)} cameras to visualizer/cameras.json")
