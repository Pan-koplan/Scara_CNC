from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction, SetEnvironmentVariable, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    # Пути к пакетам
    tb3_gazebo_share = get_package_share_directory('turtlebot3_gazebo')
    tb3_nav2_share = get_package_share_directory('turtlebot3_navigation2')
    nav_tasks_share = get_package_share_directory('tb3_aruco_mission')

    # --- Аргументы лаунча ---

    # Путь к карте
    map_yaml = LaunchConfiguration('map')
    declare_map_arg = DeclareLaunchArgument(
        'map',
        default_value=os.path.join(nav_tasks_share, 'config', 'my_map.yaml'),
        description='Полный путь к YAML-файлу карты'
    )

    # Имя мира (без .sdf) из turtlebot3_gazebo/worlds
    world_name = LaunchConfiguration('world')
    declare_world_arg = DeclareLaunchArgument(
        'world',
        default_value='turtlebot3_world_aruco',
        description='Имя world-файла (без .sdf) для запуска Gazebo'
    )

    # --- Пути к моделям для Gazebo (ArUco + TurtleBot3) ---
    gz_resource_path = SetEnvironmentVariable(
        name='GZ_SIM_RESOURCE_PATH',
        value=':'.join([
            '/opt/ros/jazzy/share/turtlebot3_gazebo/models',
            '/opt/ros/jazzy/share/turtlebot3_common/models',
            os.path.join(tb3_gazebo_share, 'worlds'),
            os.path.join(nav_tasks_share, 'models'),
        ])
    )

    # --- 1. Мир Gazebo с ArUco ---

    world_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tb3_gazebo_share, 'launch', 'turtlebot3_world.launch.py')
        ),
        launch_arguments={
            'world': world_name,  # наш aruco-мир
            'gui': 'true',        # можно поставить 'false', если GUI не нужен
        }.items()
    )

    # --- 2. Nav2 по готовой карте (без Cartographer) ---

    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tb3_nav2_share, 'launch', 'navigation2.launch.py')
        ),
        launch_arguments={
            'use_sim_time': 'true',
            'map': map_yaml,
            # при желании можно сюда же передать params_file, slam:=false и т.п.
        }.items()
    )

    # --- 3. Мост для камеры Gazebo → ROS2 ---

    bridge_node = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='gz_image_bridge',
        output='screen',
        arguments=[
            '/camera/image@sensor_msgs/msg/Image@gz.msgs.Image'
        ]
    )

    # --- 4. Детектор ArUco ---

    aruco_detector_node = Node(
        package='tb3_aruco_mission',
        executable='aruco_detector',
        name='aruco_detector',
        output='screen'
    )

    # Если хочешь, МОЖНО прямо здесь запускать какой-то nav-скрипт.
    # Например, раскомментировать это под конкретный тест:
    #
    # nav_aruco_optimal_node = Node(
    #     package='tb3_aruco_mission',
    #     executable='nav_aruco_optimal',
    #     output='screen',
    #     parameters=[{
    #         'marker_ids': [10, 20, 30, 40],
    #         'aruco_yaml': os.path.join(nav_tasks_share, 'config', 'aruco_map.yaml'),
    #     }]
    # )

    return LaunchDescription([
        declare_map_arg,
        declare_world_arg,
        gz_resource_path,

        # Сначала мир
        world_launch,

        # Через 5 секунд — Nav2
        TimerAction(period=5.0, actions=[nav2_launch]),

        # Еще через пару секунд – мост + детектор
        TimerAction(period=10.0, actions=[bridge_node, aruco_detector_node]),

        # Для автозапуска nav-скрипта можно добавить сюда nav_aruco_optimal_node
    ])
