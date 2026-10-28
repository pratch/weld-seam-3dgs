#!/bin/bash
# ==============================================================================
# Script: run_fast_lio_offline.sh
# Runs FAST-LIO2 inside Apptainer SIF on a recorded bag to generate 6-DoF odometry
# and registered point clouds for 3DGS.
# ==============================================================================

set -e

if [ "$#" -lt 1 ]; then
    echo "Usage: ./preprocess/scripts/run_fast_lio_offline.sh <bag_path> [output_prefix]"
    echo "Example: ./preprocess/scripts/run_fast_lio_offline.sh data/hero_map_bags/livox_record_longdefect119700101_000342 longdefect1"
    exit 1
fi

PROJECT_DIR="$(pwd)"
BAG_PATH="$1"
BAG_NAME=$(basename "$BAG_PATH")
PREFIX="${2:-$BAG_NAME}"

OUTPUT_ODOM_DIR="preprocess/output/odometry/${PREFIX}"
OUTPUT_CLOUD_DIR="preprocess/output/cloud_registered/${PREFIX}"
IMAGES_DIR="preprocess/output/images/${PREFIX}"
SIF_IMAGE="preprocess/fast_lio2.sif"

mkdir -p "$OUTPUT_ODOM_DIR"
mkdir -p "$OUTPUT_CLOUD_DIR"

echo "=========================================================="
echo "Starting FAST-LIO2 Offline Pipeline"
echo "Bag Path:        $BAG_PATH"
echo "Output Prefix:   $PREFIX"
echo "SIF Container:   $SIF_IMAGE"
echo "Odometry Output: $OUTPUT_ODOM_DIR"
echo "Cloud Output:    $OUTPUT_CLOUD_DIR"
echo "=========================================================="

RECORD_BAG_DIR="${OUTPUT_ODOM_DIR}/recorded_bag"
rm -rf "$RECORD_BAG_DIR"

# Launch FAST-LIO node inside container
echo "[1/4] Launching FAST-LIO2 mapping node..."
apptainer exec --bind "$PROJECT_DIR":"$PROJECT_DIR" "$SIF_IMAGE" bash -c "
    source /opt/ros/humble/setup.bash
    source /ws/install/setup.bash
    ros2 launch fast_lio mapping.launch.py \
        rviz:=false \
        use_sim_time:=true \
        config_path:=${PROJECT_DIR}/preprocess/config \
        config_file:=mid360_hero.yaml
" > "${OUTPUT_ODOM_DIR}/fast_lio.log" 2>&1 &
FAST_LIO_PID=$!
sleep 4

if ! kill -0 $FAST_LIO_PID 2>/dev/null; then
    echo "Error: FAST-LIO node failed to start. Log output:"
    cat "${OUTPUT_ODOM_DIR}/fast_lio.log"
    exit 1
fi

# Launch bag recorder inside container
echo "[2/4] Starting ROS 2 recorder for /Odometry, /cloud_registered, /path..."
apptainer exec --bind "$PROJECT_DIR":"$PROJECT_DIR" "$SIF_IMAGE" bash -c "
    source /opt/ros/humble/setup.bash
    source /ws/install/setup.bash
    ros2 bag record -o '${PROJECT_DIR}/${RECORD_BAG_DIR}' /Odometry /cloud_registered /path
" > /dev/null 2>&1 &
RECORD_PID=$!
sleep 2

# Play bag file with simulated clock
echo "[3/4] Playing bag: $BAG_PATH (rate 1.0x)..."
apptainer exec --bind "$PROJECT_DIR":"$PROJECT_DIR" "$SIF_IMAGE" bash -c "
    source /opt/ros/humble/setup.bash
    ros2 bag play '${PROJECT_DIR}/${BAG_PATH}' --clock
"

echo "Bag playback finished. Allowing buffers to flush..."
sleep 4

# Terminate recorder and FAST-LIO cleanly
kill -SIGINT $RECORD_PID 2>/dev/null || true
kill -SIGINT $FAST_LIO_PID 2>/dev/null || true
wait $RECORD_PID 2>/dev/null || true
wait $FAST_LIO_PID 2>/dev/null || true

# Post-processing
echo "[4/4] Post-processing odometry and generating 3DGS camera extrinsics..."
python3 preprocess/scripts/export_odometry.py "$RECORD_BAG_DIR" "$OUTPUT_ODOM_DIR"

if [ -d "$IMAGES_DIR" ]; then
    echo "Aligning camera frames in $IMAGES_DIR with FAST-LIO odometry..."
    python3 preprocess/scripts/align_poses_to_3dgs.py \
        "$IMAGES_DIR" \
        "${OUTPUT_ODOM_DIR}/odometry.csv" \
        "${OUTPUT_ODOM_DIR}/transforms.json"
fi

echo "Extracting registered point clouds from recorded bag to PLY..."
python3 preprocess/scripts/export_bag_pointcloud_to_ply.py \
    "$RECORD_BAG_DIR" \
    "${OUTPUT_CLOUD_DIR}/cloud_registered.ply" 5

echo "=========================================================="
echo "FAST-LIO2 Processing Succeeded!"
echo "Trajectory: ${OUTPUT_ODOM_DIR}/trajectory_tum.txt"
echo "3DGS Transforms: ${OUTPUT_ODOM_DIR}/transforms.json"
echo "=========================================================="
