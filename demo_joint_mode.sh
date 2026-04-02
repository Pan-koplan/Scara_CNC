#!/usr/bin/env bash
set -eo pipefail

PROJECT_DIR="${HOME}/Projects/Scara_arm_CNC"
WS_DIR="${PROJECT_DIR}/ros2_ws"
BACKEND_DIR="${PROJECT_DIR}/backend"
FRONTEND_DIR="${PROJECT_DIR}/frontend"

PIDS=()

cleanup() {
  echo
  echo "Останавливаю процессы..."
  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done

  sleep 1

  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  done

  echo "Все процессы остановлены."
}

trap cleanup EXIT INT TERM

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "Не найдена директория проекта: $PROJECT_DIR"
  exit 1
fi

if [[ ! -f "/opt/ros/jazzy/setup.bash" ]]; then
  echo "Не найден ROS 2 Jazzy: /opt/ros/jazzy/setup.bash"
  exit 1
fi

if [[ ! -f "${WS_DIR}/install/setup.bash" ]]; then
  echo "Не найден собранный workspace: ${WS_DIR}/install/setup.bash"
  echo "Сначала выполни сборку:"
  echo "cd ${WS_DIR} && colcon build"
  exit 1
fi

source /opt/ros/jazzy/setup.bash
source "${WS_DIR}/install/setup.bash"

echo "ROS environment загружен"
echo "PROJECT_DIR=${PROJECT_DIR}"
echo

if ! ros2 pkg executables scara_application | grep -q "web_joint_executor"; then
  echo "Не найден executable web_joint_executor в пакете scara_application"
  echo "Проверь setup.py и пересобери пакет:"
  echo "cd ${WS_DIR}"
  echo "colcon build --packages-select scara_application"
  exit 1
fi

echo "Запускаю SCARA bringup..."
(
  cd "${WS_DIR}"
  source /opt/ros/jazzy/setup.bash
  source "${WS_DIR}/install/setup.bash"
  ros2 launch scara_bringup bringup.launch.py
) &
PIDS+=($!)

sleep 5

echo "Запускаю web_joint_executor..."
(
  cd "${WS_DIR}"
  source /opt/ros/jazzy/setup.bash
  source "${WS_DIR}/install/setup.bash"
  ros2 run scara_application web_joint_executor
) &
PIDS+=($!)

sleep 2

echo "Запускаю backend..."
(
  cd "${BACKEND_DIR}"
  source /opt/ros/jazzy/setup.bash
  source "${WS_DIR}/install/setup.bash"
  python3 main.py
) &
PIDS+=($!)

sleep 2

echo "Запускаю frontend..."
(
  cd "${FRONTEND_DIR}"
  npm run dev -- --host 0.0.0.0
) &
PIDS+=($!)

sleep 2

IP_ADDR="$(hostname -I | awk '{print $1}')"

echo
echo "======================================"
echo "Демонстрация запущена"
echo "Frontend local:   http://localhost:5173"
echo "Frontend network: http://${IP_ADDR}:5173"
echo "Backend WS:       ws://localhost:8000/ws"
echo "ROS topic:        /scara/joint_goal"
echo "======================================"
echo
echo "Нажми Ctrl+C для остановки"

wait