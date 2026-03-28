from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    tb3_gazebo_share = get_package_share_directory('turtlebot3_gazebo')
    tb3_nav2_share = get_package_share_directory('turtlebot3_navigation2')

    # НЕ используем get_package_share_directory('my_maps_pkg')
    # Просто делаем дефолт как путь (можно любой существующий или пустой)
    declare_map = DeclareLaunchArgument(
        'map',
        default_value='/home/spoonge/ros2_ws/maps/my_map.yaml',
        description='Full path to map yaml file'
    )

    map_yaml = LaunchConfiguration('map')

    world_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tb3_gazebo_share, 'launch', 'turtlebot3_world.launch.py')
        ),
        launch_arguments={'gui': 'False'}.items()
    )

    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tb3_nav2_share, 'launch', 'navigation2.launch.py')
        ),
        launch_arguments={
            'use_sim_time': 'true',
            'map': map_yaml,
            # Если твой navigation2.launch.py не знает slam:=false — просто удали эту строку
            'slam': 'False',
        }.items()
    )

    return LaunchDescription([
        declare_map,
        world_launch,
        TimerAction(period=5.0, actions=[nav2_launch]),        
    ])
