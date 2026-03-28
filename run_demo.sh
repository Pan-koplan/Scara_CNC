#!/usr/bin/env bash
set -e

PROJECT_ROOT="$HOME/Projects/Scara_arm_CNC"
ROS_WS="$PROJECT_ROOT/ros2_ws"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

cleanup() {
    echo
    echo "Останавливаю демо..."
    kill $SIM_PID $EXEC_PID $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    wait 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "Подключаю окружение ROS..."
source /opt/ros/jazzy/setup.bash
source "$ROS_WS/install/setup.bash"

echo "Запускаю симуляцию..."
ros2 launch scara_bringup bringup.launch.py &
SIM_PID=$!

sleep 5

echo "Запускаю web_motion_executor..."
ros2 run scara_application web_motion_executor &
EXEC_PID=$!

sleep 2

echo "Запускаю backend..."
cd "$PROJECT_ROOT"
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

sleep 2

echo "Запускаю frontend..."
cd "$FRONTEND_DIR"

if [ ! -d node_modules ]; then
    echo "node_modules не найдены, выполняю npm install..."
    npm install
fi

npm run dev -- --host 0.0.0.0 &
FRONTEND_PID=$!

echo
echo "Демо запущено"
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "WS:       ws://localhost:8000/ws"
echo
echo "Нажми Ctrl+C для остановки"

wait
