cmake_minimum_required(VERSION 3.8)
project(scara_description)

find_package(ament_cmake REQUIRED)
find_package(xacro REQUIRED)

install(DIRECTORY
  meshes
  urdf
  config
  worlds
  models  # <--- ДОБАВИТЬ ЭТО
  DESTINATION share/${PROJECT_NAME}
)

ament_package()

