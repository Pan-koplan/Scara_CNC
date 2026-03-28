## Запуск симуляции

```bash
git clone https://github.com/Pan-koplan/Scara_CNC.git
cd Scara_CNC/ros2_ws

source /opt/ros/jazzy/setup.bash
colcon build
source install/setup.bash

ros2 launch scara_bringup bringup.launch.py
```

## Запуск ПО

./run_demo.sh

````md
# Scara_CNC

Проект демонстрирует систему управления SCARA-манипулятором через веб-интерфейс.

В текущей версии реализовано:
- симуляция робота в Gazebo
- управление через ROS 2 Jazzy
- backend на FastAPI (WebSocket)
- frontend на React (Vite)
- передача команд из веба в ROS и выполнение траекторий

---

## Архитектура

```text
Frontend (React)
        ↓ WebSocket
Backend (FastAPI)
        ↓ ROS topic
web_motion_executor (ROS 2)
        ↓ Action
ros2_control → Gazebo
````

---

## Требования

* Ubuntu 24.04
* ROS 2 Jazzy
* Gazebo (ros_gz)
* Python 3
* Node.js 22 + npm

---

## Быстрый старт

```bash
git clone https://github.com/Pan-koplan/Scara_CNC.git
cd Scara_CNC

./setup_demo.sh
./run_demo.sh
```

После запуска:

* Frontend: [http://localhost:5173](http://localhost:5173)
* Backend: [http://localhost:8000](http://localhost:8000)
* WebSocket: ws://localhost:8000/ws

---

## Установка (вручную)

### 1. Backend

```bash
cd backend
python3 -m pip install -r requirements.txt
cd ..
```

### 2. Node.js 22

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc

nvm install 22
nvm use 22
nvm alias default 22
```

### 3. Frontend

```bash
cd frontend
npm install
cd ..
```

### 4. ROS 2 workspace

```bash
cd ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build
source install/setup.bash
cd ..
```

---

## Ручной запуск

### Симуляция

```bash
cd ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch scara_bringup bringup.launch.py
```

### Исполнитель команд

```bash
ros2 run scara_application web_motion_executor
```

### Backend

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm run dev -- --host 0.0.0.0
```

---

## Использование

В веб-интерфейсе доступны:

* пресеты:

  * HOME
  * POINT_A
  * POINT_B
* ручной ввод координат X/Y
* отправка команд роботу
* отображение статуса и ответа сервера

---

## Доступ с телефона

1. Подключить телефон и компьютер к одной сети
2. Узнать IP компьютера:

```bash
hostname -I
```

3. Открыть в браузере:

```text
http://<IP_КОМПЬЮТЕРА>:5173
```

---

## Структура проекта

```text
Scara_CNC/
├── backend/
├── frontend/
├── ros2_ws/
├── run_demo.sh
├── setup_demo.sh
└── README.md
```

---

## Известные ограничения

* работает в режиме симуляции
* требует установленный ROS 2 Jazzy на хосте
* Docker-конфигурация не покрывает полный стек

---

## Дальнейшее развитие

* цифровой двойник в веб-интерфейсе
* визуализация положения робота
* режим real hardware (ESP32)
* интеграция с ЧПУ

```
```
