from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'scara_application'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='spoonge',
    maintainer_email='Obeyoranother@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'simple_mover = scara_application.simple_mover:main',
            'part_4_points = scara_application.part_4_points:main',
            'MoveIT_cnc_coop = scara_application.MoveIT_cnc_coop:main',
	    'web_goal_listener = scara_application.web_goal_listener:main',
	    'web_motion_executor = scara_application.web_motion_executor:main',
        ],
    },
)
