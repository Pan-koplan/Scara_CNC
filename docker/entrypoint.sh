#!/usr/bin/env bash
set -e

source /opt/ros/jazzy/setup.bash
source /app/ros2_ws/install/setup.bash

MODE="${MODE:-hw}"

if [ "$MODE" = "sim" ]; then
  echo "Starting simulation mode..."
  ros2 launch scara_bringup bringup.launch.py use_rviz:=false &
  SIM_PID=$!

  sleep 6
  ros2 run scara_application web_motion_executor &
  EXEC_PID=$!
else
  echo "Starting hardware mode..."
  # Тут должен быть твой hardware bringup без Gazebo
  # Пример:
  # ros2 launch scara_bringup hardware.launch.py serial_port:=${SERIAL_PORT:-/dev/ttyUSB0} &
  # HW_PID=$!

  ros2 run scara_application web_motion_executor &
  EXEC_PID=$!
fi

exec python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000