import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, RegisterEventHandler, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch.event_handlers import OnProcessExit
import xacro
from launch.actions import IncludeLaunchDescription, RegisterEventHandler, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.event_handlers import OnProcessExit

def generate_launch_description():
	pkg_name = 'scara_description'
	# Исправленный блок путей
	pkg_share = get_package_share_directory(pkg_name)
	models_dir = os.path.join(pkg_share, 'models')
	# Это путь к папке share, где лежат все пакеты
	# Get the share directory for both packages
	pkg_scara_sim = get_package_share_directory('scara_sim')
	pkg_scara_description = get_package_share_directory('scara_description')

	# Path to the 'models' directory where 'table' and 'detail' live
	# This matches the 'model://table' URI because Gazebo looks INSIDE this folder
	gz_models_path = os.path.join(pkg_scara_sim, 'models')

	# Global share for resolving package:// URIs
	workspace_share = os.path.dirname(pkg_scara_description)

	resource_path = gz_models_path + ':' + workspace_share + ':' + os.environ.get('GZ_SIM_RESOURCE_PATH', '')

	gz_resource_path = SetEnvironmentVariable(
		name='GZ_SIM_RESOURCE_PATH',
		value=resource_path
	)

	urdf_file = os.path.join(pkg_share, 'urdf', 'scara.xacro')

	doc = xacro.process_file(urdf_file)
	robot_description_content = doc.toxml()

	# Найдите полный путь к файлу мира
	world_path = os.path.join(pkg_share, 'worlds', 'lab.sdf')

	gz_sim = IncludeLaunchDescription(
	PythonLaunchDescriptionSource(
	    os.path.join(get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')
	),
	# Передаем полный путь world_path вместо просто имени 'lab.sdf'
	launch_arguments={'gz_args': ['-r ', world_path]}.items(),
	)

	spawn_entity = Node(
	package='ros_gz_sim',
	executable='create',
	arguments=[
	    '-name', 'scara',
	    '-string', robot_description_content,
	    '-x', '0.7', 
	    '-y', '-0.5', 
	    '-z', '1',
	    '-R', '0.0',
	    '-P', '0.0',
	    '-Y', '1.5708', # Поворот на 90 градусов (Пи/2)
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

	# joint_state_broadcaster_spawner = Node(
	# package='controller_manager',
	# executable='spawner',
	# arguments=['joint_state_broadcaster', '--controller-manager', '/controller_manager'],
	# )

	# scara_controller_spawner = Node(
	# package='controller_manager',
	# executable='spawner',
	# arguments=['scara_controller', '--controller-manager', '/controller_manager'],
	# )
	# gripper_controller_spawner = Node(
	#     package='controller_manager',
	#     executable='spawner',
	#     arguments=['gripper_controller', '--controller-manager', '/controller_manager'],
	# )
	controllers_launch = IncludeLaunchDescription(
		PythonLaunchDescriptionSource(
			os.path.join(
				get_package_share_directory('scara_control'),
				'launch',
				'controllers.launch.py'
			)
		)
	)
	return LaunchDescription([
		gz_resource_path,
		gz_sim,
		node_robot_state_publisher,
		spawn_entity,
		bridge,
		# RegisterEventHandler(
		# 	event_handler=OnProcessExit(
		# 	target_action=spawn_entity,
		# 	on_exit=[joint_state_broadcaster_spawner],
		# 	)
		# ),
		# RegisterEventHandler(
		# 	event_handler=OnProcessExit(
		# 	target_action=joint_state_broadcaster_spawner,
		# 	on_exit=[scara_controller_spawner],
		# 	)
		# ),
		# RegisterEventHandler(
		# 	event_handler=OnProcessExit(
		# 	target_action=joint_state_broadcaster_spawner,
		# 	on_exit=[gripper_controller_spawner],
		# 	)
		# ),
		RegisterEventHandler(
			event_handler=OnProcessExit(
				target_action=spawn_entity,
				on_exit=[controllers_launch],
			)
		),
	])
