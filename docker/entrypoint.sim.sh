#!/usr/bin/env bash
set -e

source /opt/ros/jazzy/setup.bash
source /app/ros2_ws/install/setup.bash

ros2 launch scara_bringup bringup.launch.py use_rviz:=false &
sleep 8

ros2 run scara_application web_motion_executor &

exec python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000