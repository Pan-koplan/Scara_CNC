FROM ros:jazzy-ros-base AS base

SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get update && \
    apt-get install -y \
    python3-pip \
    python3-venv \
    python3-setuptools \
    python3-packaging \
    python3-catkin-pkg \
    python3-empy \
    python3-lark \
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
    ros-jazzy-moveit \
    ros-jazzy-moveit-common \
    ros-jazzy-moveit-ros-planning-interface \
    ros-jazzy-moveit-planners-ompl \
    nodejs \
    npm && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt

RUN python3 -m venv /opt/venv --system-site-packages && \
    source /opt/venv/bin/activate && \
    pip install --upgrade pip && \
    pip install --no-cache-dir catkin_pkg && \
    pip install --no-cache-dir -r /app/backend/requirements.txt

ENV PATH="/opt/venv/bin:$PATH"

COPY frontend /app/frontend
RUN cd /app/frontend && npm install && npm run build

COPY ros2_ws /app/ros2_ws
COPY backend /app/backend
COPY docker/entrypoint.hw.sh /entrypoint.hw.sh
COPY docker/entrypoint.sim.sh /entrypoint.sim.sh

RUN chmod +x /entrypoint.hw.sh /entrypoint.sim.sh

RUN rosdep update || true

RUN mkdir -p /app/backend/static && \
    cp -r /app/frontend/dist/* /app/backend/static/

FROM base AS hw

RUN rm -rf /app/ros2_ws/build /app/ros2_ws/install /app/ros2_ws/log && \
    source /opt/ros/jazzy/setup.bash && \
    cd /app/ros2_ws && \
    colcon build --symlink-install \
      --packages-up-to \
        scara_bringup \
        scara_application \
      --packages-skip scara_sim scara_moveit_config scara_mtc

EXPOSE 8000
ENTRYPOINT ["/entrypoint.hw.sh"]

FROM base AS sim

RUN apt-get update && apt-get install -y \
    ros-jazzy-gz-ros2-control \
    ros-jazzy-ros-gz \
    ros-jazzy-ros-gz-sim \
    ros-jazzy-ros-gz-bridge \
    ros-jazzy-moveit-task-constructor-core \
    ros-jazzy-moveit-task-constructor-msgs \
    && rm -rf /var/lib/apt/lists/*

RUN rm -rf /app/ros2_ws/build /app/ros2_ws/install /app/ros2_ws/log && \
    source /opt/ros/jazzy/setup.bash && \
    cd /app/ros2_ws && \
    colcon build --symlink-install \
      --packages-up-to \
        scara_bringup \
        scara_application \
        scara_sim \
        scara_moveit_config \
      --packages-skip scara_mtc

# Копируем бэкенд
COPY backend/ /app/backend/

# Копируем сборку фронтенда (должна быть собрана заранее!)
COPY frontend/dist/ /app/backend/static/

WORKDIR /app/backend
CMD ["python", "main.py"]

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sim.sh"]