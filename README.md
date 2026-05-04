```markdown
xhost +local:docker
# 🔧 Разработка (с hot-reload)
ENV=development docker-compose --profile dev up

# 🎮 Симуляция
ENV=production docker-compose --profile sim up

# 🔌 Реальное железо
ENV=production docker-compose --profile hw up

# 🧪 Только бэкенд для тестов API
cd backend && uvicorn src.main:app --reload

# 🎨 Только фронтенд (прокси на локальный бэкенд)
cd frontend && npm run dev

### Запуск с реальным роботом

```bash
# Подключи контроллер по USB (/dev/ttyUSB0)
docker compose --profile hw up
```

### Остановка

```bash
docker compose --profile sim down
# или
docker compose --profile hw down
```

### После запуска

| Компонент | Адрес |
|-----------|-------|
| 🌐 Веб-интерфейс | [http://localhost:8000](http://localhost:8000) |
| 🔌 WebSocket | `ws://localhost:8000/ws` |
| 🧪 ROS topics | `docker exec -it scara_robot_sim bash` → `ros2 topic list` |

---

## 🛠 Разработка (горячая перезагрузка)

### Архитектура с volumes

```yaml
# docker-compose.yml
volumes:
  - ./backend:/app/backend          # hot-reload для FastAPI
  - ./ros2_ws/src:/app/ros2_ws/src  # активная разработка ROS-пакетов
```

### Изменения применяются мгновенно:

- Правки в `backend/*.py` → авто-релоад через uvicorn
- Правки в `ros2_ws/src/*` → `colcon build` внутри контейнера
- Правки в `frontend/*` → запусти Vite dev отдельно (см. ниже)

### Frontend в dev-режиме (опционально)

Если хочешь hot-reload для React:

```bash
# В одном терминале — Docker без фронтенда
docker compose --profile sim up --no-start  # только поднимает ROS

# В другом — Vite dev server
cd frontend
npm install
npm run dev  # → http://localhost:5173
```

> В этом режиме фронтенд обращается к бэкенду на `http://localhost:8000`

---

## 🧩 Ручной запуск (без Docker)

> Для отладки или если Docker не подходит

### Требования

- Ubuntu 24.04, ROS 2 Jazzy, Python 3.10+, Node.js 22+

### Установка

```bash
# 1. ROS workspace
cd ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build
source install/setup.bash

# 2. Backend
cd ../backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Frontend
cd ../frontend
npm install
```

### Запуск (4 терминала)

```bash
# Терминал 1: симуляция
source ros2_ws/install/setup.bash
ros2 launch scara_bringup bringup.launch.py

# Терминал 2: backend
source ros2_ws/install/setup.bash
source backend/venv/bin/activate
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Терминал 3: frontend
cd frontend && npm run dev

# Терминал 4 (опционально): отладка ROS
ros2 topic echo /joint_states
```

---

## 🏗 Архитектура

```
┌─────────────────┐
│   Browser       │
│   (React/Vite)  │
└──────┬──────────┘
       │ HTTP/WebSocket
       ▼
┌─────────────────┐
│   FastAPI       │
│   (backend/)    │
└────────────────┘
       │ rclpy / ROS 2 API
       ▼
┌─────────────────┐
│   ROS 2 Nodes   │
│   • web_bridge_node    │
│   • web_motion_executor│
│   • ros2_control     │
└────────────────┘
       │
   ┌───┴───┐
   ▼       ▼
[Gazebo] [ESP32/Real HW]
```

### Ключевые компоненты

| Компонент | Назначение |
|-----------|------------|
| `web_bridge_node` | Мост WebSocket → ROS topics |
| `web_motion_executor` | Исполнение траекторий через Action Server |
| `scara_controller` | `JointTrajectoryController` для управления суставами |
| `gz_ros2_control` | Связка Gazebo ↔ ros2_control |

---

## ⚙️ Конфигурация

### Профили Docker

| Профиль | Сервис | Назначение |
|---------|--------|------------|
| `sim` | `robot_sim` | Симуляция в Gazebo + GUI |
| `hw` | `robot_hw` | Работа с реальным манипулятором |

### Переменные окружения

```env
# .env (опционально)
DISPLAY=:0                    # для GUI в симуляции
SERIAL_PORT=/dev/ttyUSB0      # для hw-режима
```

---

## 📱 Доступ с других устройств

1. Подключи устройство к той же сети
2. Узнай IP хоста: `hostname -I`
3. Открой: `http://<IP>:8000`

> Для WebSocket убедись, что нет блокировок фаервола на порт 8000.

---

## 🐛 Диагностика

### Контейнер не видит X11

```bash
xhost +local:docker
docker compose --profile sim up
```

### ROS пакет не найден

```bash
docker exec -it scara_robot_sim bash
source /app/ros2_ws/install/setup.bash
ros2 pkg list | grep scara
```

### Фронтенд — белый экран

- Проверь консоль браузера (F12 → Console)
- Убедись, что `/assets/*.js` возвращают `200` и `application/javascript`
- Очисти кэш браузера (Ctrl+Shift+R)

### Контроллер не активируется

```bash
docker exec -it scara_robot_sim bash
ros2 control list_controllers
ros2 topic echo /scara_controller/joint_trajectory --once
```

### Backend не перезагружается

- Убедись, что volume подключен: `docker inspect scara_robot_sim | grep -A 5 Mounts`
- Проверь логи: `docker compose logs -f robot_sim | grep "Will watch for changes"`

---

## 🗂 Структура проекта

```
Scara_CNC/
├── docker/
│   ├── Dockerfile           # multi-stage: base/sim/hw
│   ├── entrypoint.sim.sh    # запуск симуляции
│   └── entrypoint.hw.sh     # запуск с железом
├── backend/
│   ├── main.py              # FastAPI + WebSocket + ROS bridge
│   ├── requirements.txt
│   └── static/              # собранный frontend (production)
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # основной компонент
│   │   └── main.jsx         # точка входа
│   ├── vite.config.js
│   └── package.json
├── ros2_ws/
│   └── src/
│       ├── scara_bringup/       # launch-файлы
│       ├── scara_control/       # ros2_control config
│       ├── scara_sim/           # Gazebo worlds/models
│       ├── scara_application/   # web_motion_executor, web_bridge_node
│       └── ...
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

## 📋 Чеклист перед пушем

- [ ] `docker compose --profile sim up` работает с чистого клона
- [ ] `xhost +local:docker` задокументировано
- [ ] В `.gitignore` нет `build/`, `install/`, `node_modules/`
- [ ] README отражает актуальный workflow
- [ ] Все правки в `backend/main.py` закоммичены

---

## 🚧 Известные ограничения

- Требуется `xhost +local:docker` для GUI в симуляции
- При первом запуске сборка образа может занять 10–20 минут
- Для hw-режима нужен доступ к `/dev/ttyUSB0` (udev правила)
- Frontend в production режиме — статические файлы, нет hot-reload

---

## 🔮 Планы развития

- [ ] Цифровой двойник: визуализация положения в реальном времени
- [ ] Поддержка траекторий из G-code
- [ ] Режим ESP32: управление по UART/Bluetooth
- [ ] Мультиконтейнерная архитектура (ROS/backend/frontend отдельно)

---

## 💡 Советы по разработке

### Быстрая пересборка

```bash
# Только backend (с volumes)
docker compose restart robot_sim

# С пересборкой образа
docker compose up -d --build robot_sim

# Полная пересборка без кэша
docker compose build --no-cache robot_sim
```

### Отладка ROS внутри контейнера

```bash
docker exec -it scara_robot_sim bash
source /app/ros2_ws/install/setup.bash

# Просмотр топиков
ros2 topic list
ros2 topic echo /joint_states

# Управление контроллерами
ros2 control list_controllers
ros2 topic pub /scara_controller/joint_trajectory ...
```

### Логирование

```bash
# Все логи
docker compose logs -f robot_sim

# Только ROS
docker compose logs -f robot_sim | grep "\[INFO\]"

# Только backend
docker compose logs -f robot_sim | grep "INFO:     "
```

---

> 💡 **Совет**: Для разработки используй `volumes` — изменения в коде применяются мгновенно без `docker build`.

---

## 📄 Лицензия

MIT License — см. файл LICENSE

## 👥 Авторы

- **spoonge** ([@Pan-koplan](https://github.com/Pan-koplan))

---

**Happy Coding! 🚀**
```
