## Запуск симуляции

```bash
git clone https://github.com/Pan-koplan/Scara_CNC.git
cd Scara_CNC/ros2_ws

source /opt/ros/jazzy/setup.bash
colcon build
source install/setup.bash

ros2 launch scara_bringup bringup.launch.py
```
