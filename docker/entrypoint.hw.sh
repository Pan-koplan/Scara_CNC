#!/usr/bin/env bash
set -e

source /opt/ros/jazzy/setup.bash
source /app/ros2_ws/install/setup.bash

# Здесь должен быть реальный bringup железа
# Например:
# ros2 launch scara_bringup hardware.launch.py serial_port:=${SERIAL_PORT:-/dev/ttyUSB0} &
# Пока временно просто backend:
ros2 run scara_application web_motion_executor &

exec python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000