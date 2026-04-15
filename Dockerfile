FROM ros:jazzy-ros-base

SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# Системные зависимости
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-vcstool \
    ros-jazzy-xacro \
    ros-jazzy-robot-state-publisher \
    ros-jazzy-controller-manager \
    ros-jazzy-joint-state-broadcaster \
    ros-jazzy-position-controllers \
    ros-jazzy-ros2-control \
    ros-jazzy-ros2-controllers \
    ros-jazzy-tf2-ros \
    ros-jazzy-geometry-msgs \
    ros-jazzy-std-msgs \
    ros-jazzy-launch-ros \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Python backend deps
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip3 install --no-cache-dir -r /app/backend/requirements.txt

# Frontend build
COPY frontend /app/frontend
RUN cd /app/frontend && npm install && npm run build

# Repo contents
COPY ros2_ws /app/ros2_ws
COPY backend /app/backend
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# rosdep init может уже быть в образе, но harmless guard
RUN rosdep update || true

# Сборка workspace
RUN source /opt/ros/jazzy/setup.bash && \
    cd /app/ros2_ws && \
    colcon build --symlink-install

# Сложим frontend dist рядом с backend static
RUN mkdir -p /app/backend/static && \
    cp -r /app/frontend/dist/* /app/backend/static/

ENV ROS_WS=/app/ros2_ws
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]