FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-c"]

# Install build dependencies, PCL, and Eigen
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    libpcl-dev \
    libeigen3-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    ros-humble-pcl-conversions \
    ros-humble-pcl-ros \
    ros-humble-rviz2 \
    ros-humble-rosbag2 \
    ros-humble-rosbag2-storage-mcap \
    python3-colcon-common-extensions \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies for trajectory handling
RUN pip3 install --no-cache-dir numpy scipy opencv-python rosbags

# Create ROS 2 workspace
WORKDIR /ws/src

# Clone livox_ros_driver2 (for CustomMsg)
RUN git clone --depth 1 https://github.com/Livox-SDK/livox_ros_driver2.git && \
    cd livox_ros_driver2 && \
    ./build.sh ROS2

# Clone FAST_LIO ROS 2 port
RUN git clone --depth 1 https://github.com/Ericsii/FAST_LIO_ROS2.git fast_lio

# Build the workspace
WORKDIR /ws
RUN source /opt/ros/humble/setup.bash && \
    colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release

# Environment setup
RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc && \
    echo "source /ws/install/setup.bash" >> ~/.bashrc

WORKDIR /workspace
ENTRYPOINT ["/bin/bash", "-c", "source /ws/install/setup.bash && exec \"$@\"", "--"]
CMD ["bash"]
