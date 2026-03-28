import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from moveit_configs_utils import MoveItConfigsBuilder

def generate_launch_description():
    # ---------- Аргументы ----------
    use_sim = LaunchConfiguration("use_sim")
    use_moveit = LaunchConfiguration("use_moveit")
    use_rviz = LaunchConfiguration("use_rviz")
    
    # Новые флаги для ЧПУ
    run_cnc_logic = LaunchConfiguration("run_cnc_logic")
    run_coop_scenario = LaunchConfiguration("run_coop_scenario")

    world = LaunchConfiguration("world")
    controllers_delay = LaunchConfiguration("controllers_delay")
    moveit_delay = LaunchConfiguration("moveit_delay")
    cnc_delay = LaunchConfiguration("cnc_delay") # Задержка для скрипта кооперации

    declare_args = [
        DeclareLaunchArgument("use_sim", default_value="true"),
        DeclareLaunchArgument("use_moveit", default_value="true"),
        DeclareLaunchArgument("use_rviz", default_value="true"),
        DeclareLaunchArgument("spawn_controllers", default_value="true"),
        
        # Управление логикой станка
        DeclareLaunchArgument("run_cnc_logic", default_value="true", description="Run CNC machine service node"),
        DeclareLaunchArgument("run_coop_scenario", default_value="true", description="Run the main coop script"),
        DeclareLaunchArgument("cnc_delay", default_value="12.0", description="Delay before starting coop scenario"),

        DeclareLaunchArgument(
            "world",
            default_value=PathJoinSubstitution([FindPackageShare("scara_sim"), "worlds", "lab.sdf"]),
            description="Path to Gazebo world"
        ),

        DeclareLaunchArgument("controllers_delay", default_value="3.0"),
        DeclareLaunchArgument("moveit_delay", default_value="7.0"),
    ]

    # ---------- 1. Симуляция (Gazebo + Robot State Publisher) ----------
    sim_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare("scara_sim"), "launch", "sim_scara.launch.py"])
        ),
        condition=IfCondition(use_sim),
        launch_arguments={"world": world}.items()
    )

    # ---------- 2. Контроллеры ----------
    controllers_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare("scara_control"), "launch", "controllers.launch.py"])
        ),
        condition=IfCondition(LaunchConfiguration("spawn_controllers")),
    )

    controllers_launch_delayed = TimerAction(
        period=controllers_delay,
        actions=[controllers_launch],
    )

    # ---------- 3. MoveIt 2 ----------
    moveit_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare("scara_moveit_config"), "launch", "move_group.launch.py"])
        ),
        condition=IfCondition(use_moveit),
        launch_arguments={"use_rviz": use_rviz}.items()
    )

    moveit_launch_delayed = TimerAction(
        period=moveit_delay,
        actions=[moveit_launch],
    )

    # ---------- 4. Нода Станка (Service Server) ----------
    # Запускается почти сразу, так как это просто сервис
    cnc_machine_node = Node(
        package="scara_cnc", # Пакет, где лежит cnc_node.py
        executable="cnc_node",
        output="screen",
        condition=IfCondition(run_cnc_logic),
        parameters=[{"use_sim_time": use_sim}]
    )

    # ---------- 5. Главный сценарий (Coop Script) ----------
    # Это твоя нода test_cnc_coop.py, которая ждет робота и станок
    coop_scenario_node = Node(
        package="scara_application",
        executable="test_cnc_coop",
        output="screen",
        condition=IfCondition(run_coop_scenario),
        parameters=[{"use_sim_time": use_sim}]
    )

    # Запускаем сценарий самым последним, когда MoveIt и Станок точно готовы
    coop_scenario_delayed = TimerAction(
        period=cnc_delay,
        actions=[coop_scenario_node],
    )

    return LaunchDescription(
        declare_args + [
            sim_launch,
            controllers_launch_delayed,
            moveit_launch_delayed,
            cnc_machine_node,
            coop_scenario_delayed,
        ]
    )
