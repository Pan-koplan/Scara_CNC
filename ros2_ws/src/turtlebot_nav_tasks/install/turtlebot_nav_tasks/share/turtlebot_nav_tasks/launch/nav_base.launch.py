from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    # Пути к чужим пакетам
    tb3_gazebo_share = get_package_share_directory('turtlebot3_gazebo')
    tb3_cartographer_share = get_package_share_directory('turtlebot3_cartographer')
    tb3_nav2_share = get_package_share_directory('turtlebot3_navigation2')

    # 1. Мир Gazebo с TurtleBot3
    world_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tb3_gazebo_share, 'launch', 'turtlebot3_world.launch.py')
        ),
        launch_arguments={'gui': 'false'}.items()
    )

    # 2. SLAM (Cartographer) с use_sim_time
    slam_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tb3_cartographer_share, 'launch', 'cartographer.launch.py')
        ),
        launch_arguments={'use_sim_time': 'true'}.items()
    )

    # 3. Навигация Nav2
    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tb3_nav2_share, 'launch', 'navigation2.launch.py')
        ),
        launch_arguments={'use_sim_time': 'true'}.items()
    )

    # TimerAction, чтобы всё не стартовало в одну секунду
    # (даём миру и SLAM чуть подняться)
    return LaunchDescription([
        world_launch,
        TimerAction(period=5.0, actions=[slam_launch]),
        TimerAction(period=10.0, actions=[nav2_launch]),
    ])
