import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, RegisterEventHandler, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch.event_handlers import OnProcessExit
import xacro

def generate_launch_description():
    pkg_name = 'scara_cnc'
    pkg_share = get_package_share_directory(pkg_name)
    
    # --- ИСПРАВЛЕНИЕ ПУТЕЙ К МЕШАМ ---
    # Мы берем путь к share (обычно install/scara_cnc/share/scara_cnc)
    # И поднимаемся на уровень выше, чтобы Gazebo нашел папку "scara_cnc"
    install_dir = os.path.dirname(pkg_share)
    
    # Добавляем путь к ресурсам в переменную окружения
    # Если URDF использует package://scara_cnc/..., Gazebo будет искать папку scara_cnc внутри этих путей
    gz_resource_path = SetEnvironmentVariable(
        name='GZ_SIM_RESOURCE_PATH',
        value=[
            install_dir, 
            ":", 
            os.environ.get('GZ_SIM_RESOURCE_PATH', '') # Сохраняем старые пути, если были
        ]
    )
    # ---------------------------------

    urdf_file = os.path.join(pkg_share, 'urdf', 'scara.urdf')
    
    doc = xacro.process_file(urdf_file)
    robot_description_content = doc.toxml()

    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={'gz_args': '-r empty.sdf'}.items(),
    )

    spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-name', 'scara',
            '-string', robot_description_content,
            '-x', '0', '-y', '0', '-z', '0.05',
            '-allow_renaming', 'false'
        ],
        output='screen'
    )

    node_robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description_content,
            'use_sim_time': True
        }]
    )

    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock',
            '/tf@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V',
            '/tf_static@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V',
        ],
        output='screen'
    )

    joint_state_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster', '--controller-manager', '/controller_manager'],
    )

    scara_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['scara_controller', '--controller-manager', '/controller_manager'],
    )
    simple_mover_node = Node(
        package='scara_cnc',
        executable='simple_mover',   # имя из setup.py/entry_points или установленного файла
        output='screen'
    )

    return LaunchDescription([
        gz_resource_path,
        gz_sim,
        node_robot_state_publisher,
        spawn_entity,
        bridge,
        RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=spawn_entity,
                on_exit=[joint_state_broadcaster_spawner],
            )
        ),
        RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=joint_state_broadcaster_spawner,
                on_exit=[scara_controller_spawner],
            )
        ),
        RegisterEventHandler(
          OnProcessExit(
            target_action=scara_controller_spawner,
            on_exit=[simple_mover_node]
          )
        )
    ])
