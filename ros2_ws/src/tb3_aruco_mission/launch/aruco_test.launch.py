from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration
from launch.actions import DeclareLaunchArgument

import os


def generate_launch_description():

    world_path = "/home/spoonge/ros2_ws/src/turtlebot3_simulations/turtlebot3_gazebo/worlds/turtlebot3_world_aruco.sdf"
    

    return LaunchDescription([

        # -----------------------------
        # 1. Запускаем Gazebo с миром
        # -----------------------------
        ExecuteProcess(
            cmd=[
                'gz', 'sim', world_path
            ],
            output='screen'
        ),

        # -----------------------------
        # 2. ros_gz_bridge для камеры
        # -----------------------------
        ExecuteProcess(
            cmd=[
                "ros2", "run", "ros_gz_bridge", "parameter_bridge",
                "/camera/image@sensor_msgs/msg/Image@gz.msgs.Image"
            ],
            output='screen'
        ),

        # --------------------------------
        # 3. Узел ArUco-детектора
        # --------------------------------
        Node(
            package='tb3_aruco_mission',
            executable='aruco_detector',
            name='aruco_detector',
            output='screen',
            parameters=[
                {"image_topic": "/camera/image"}  # если у тебя image_raw → поменяем
            ]
        ),
    ])
