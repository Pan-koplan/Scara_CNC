from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction, GroupAction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from moveit_configs_utils import MoveItConfigsBuilder
import os

def generate_launch_description():
    # ---------- Args ----------
    use_sim = LaunchConfiguration("use_sim")
    use_moveit = LaunchConfiguration("use_moveit")
    use_rviz = LaunchConfiguration("use_rviz")
    run_application = LaunchConfiguration("run_application")

    world = LaunchConfiguration("world")
    controllers_delay = LaunchConfiguration("controllers_delay")
    moveit_delay = LaunchConfiguration("moveit_delay")
    app_delay = LaunchConfiguration("app_delay")

    run_mtc = LaunchConfiguration("run_mtc")
    mtc_delay = LaunchConfiguration("mtc_delay")
    
    

    declare_args = [
        DeclareLaunchArgument("run_mtc", default_value="false"),
        DeclareLaunchArgument("mtc_delay", default_value="10.0"),
        DeclareLaunchArgument("use_sim", default_value="true"),
        DeclareLaunchArgument("use_moveit", default_value="true"),
        DeclareLaunchArgument("use_rviz", default_value="true"),
        DeclareLaunchArgument("run_application", default_value="false"),
        DeclareLaunchArgument("spawn_controllers", default_value="true"),
        

        DeclareLaunchArgument(
            "world",
            default_value=PathJoinSubstitution([
                FindPackageShare("scara_sim"),
                "worlds",
                "lab.sdf",
            ]),
            description="Path to Gazebo world (.sdf)"
        ),

        # delays allow Gazebo/entity/controller_manager to appear before spawners & move_group
        DeclareLaunchArgument("controllers_delay", default_value="3.0"),
        DeclareLaunchArgument("moveit_delay", default_value="6.0"),
        DeclareLaunchArgument("app_delay", default_value="8.0"),
    ]

    # ---------- Include: Simulation ----------
    sim_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare("scara_sim"),
                "launch",
                "sim_scara.launch.py"
            ])
        ),
        condition=IfCondition(use_sim),
        launch_arguments={
            "world": world,
        }.items()
    )

    # ---------- Include: MoveIt ----------
    moveit_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare("scara_moveit_config"),
                "launch",
                "move_group.launch.py"
            ])
        ),
        condition=IfCondition(use_moveit),
        launch_arguments={
            "use_rviz": use_rviz,
        }.items()
    )

    moveit_launch_delayed = TimerAction(
        period=moveit_delay,
        actions=[moveit_launch],
    )

    # ---------- Application node (example: simple_mover) ----------
    # Запускаем позже, когда move_group и контроллеры уже готовы.
    app_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare("scara_application"),
                "launch",
                "application.launch.py"
            ])
        ),
        condition=IfCondition(run_application),
        launch_arguments={}.items()
    )

    app_launch_delayed = TimerAction(
        period=app_delay,
        actions=[app_launch],
    )
    # ---------- MTC node (hello) ----------
    # 1. Строим полный путь к файлу xacro
    xacro_file = os.path.join(
        get_package_share_directory("scara_description"),
        "urdf",
        "scara.xacro"
    )

    # 2. Собираем конфиг MoveIt
    moveit_config = (
        MoveItConfigsBuilder("scara", package_name="scara_moveit_config") # <- Тут оставляем moveit_config!
        .robot_description(file_path=xacro_file) # <- А путь к файлу передаем явно
        .to_moveit_configs()
        )
    
    mtc_node = Node(
        package="scara_mtc",
        executable="mtc_node",
        output="screen",
        condition=IfCondition(run_mtc),
        parameters=[
            moveit_config.to_dict(),      # <-- ключевое: robot_description + SRDF + kinematics + planners
            {"use_sim_time": use_sim},    # use_sim у тебя LaunchConfiguration("use_sim")
            {"arm_group": "scara_arm"},
            {"home_named_target": "home"},
            {"plan_on_start": True},
        ],
    )
    
    mtc_node_delayed = TimerAction(
        period=mtc_delay,
        actions=[mtc_node],
    )
    

    return LaunchDescription(
        declare_args + [
            sim_launch,
            moveit_launch_delayed,
            mtc_node_delayed,  
            app_launch_delayed,
        ]
    )
