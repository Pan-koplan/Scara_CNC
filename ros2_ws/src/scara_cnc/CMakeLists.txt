cmake_minimum_required(VERSION 3.8)
project(scara_cnc)

find_package(ament_cmake REQUIRED)

# 1. Копируем ресурсы (URDF, меши, лаунчи) в папку share
install(
  DIRECTORY urdf meshes launch config
  DESTINATION share/${PROJECT_NAME}
)

# Установка Python-скрипта как исполняемого файла
install(PROGRAMS
  scara_cnc/cnc_node.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
