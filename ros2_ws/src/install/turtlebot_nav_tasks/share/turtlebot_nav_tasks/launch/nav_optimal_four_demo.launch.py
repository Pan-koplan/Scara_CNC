from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    # Пакеты TurtleBot3
    tb3_gazebo = get_package_share_directory('turtlebot3_gazebo')
    tb3_cartographer = get_package_share_directory('turtlebot3_cartographer')
    tb3_nav2 = get_package_share_directory('turtlebot3_navigation2')

    # 1) Мир Gazebo
    world = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tb3_gazebo, 'launch', 'turtlebot3_world.launch.py')
        ),
        launch_arguments={
            'gui': 'false',        # можешь поставить 'true', если нужен GUI
        }.items()
    )

    # 2) SLAM (Cartographer)
    slam = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tb3_cartographer, 'launch', 'cartographer.launch.py')
        ),
        launch_arguments={
            'use_sim_time': 'true',
        }.items()
    )

    # 3) Navigation2
    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tb3_nav2, 'launch', 'navigation2.launch.py')
        ),
        launch_arguments={
            'use_sim_time': 'true',
        }.items()
    )

    # 4) Наш узел оптимизации маршрута из 4 точек
    optimal_four = Node(
        package='turtlebot_nav_tasks',
        executable='nav_optimal_four',
        output='screen'
    )

    # Порядок:
    #   сразу — Gazebo
    #   через 5 сек — SLAM
    #   через 10 сек — Nav2
    #   через 20 сек — наш скрипт
    return LaunchDescription([
        world,
        TimerAction(period=5.0, actions=[slam]),
        TimerAction(period=10.0, actions=[nav2]),
        TimerAction(period=20.0, actions=[optimal_four]),
    ])
