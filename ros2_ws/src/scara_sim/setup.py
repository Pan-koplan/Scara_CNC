from setuptools import find_packages, setup
import os
from glob import glob
from setuptools import setup, find_packages

package_name = 'scara_sim'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'worlds'), glob('worlds/*.sdf')),
        
        # Map the 'worlds/table' folder to 'share/scara_sim/models/table'
        (os.path.join('share', package_name, 'models/table'), glob('worlds/table/*.sdf')),
        (os.path.join('share', package_name, 'models/table'), glob('worlds/table/*.config')),
        (os.path.join('share', package_name, 'models/table/meshes'), glob('worlds/table/meshes/*')),
        
        # Map the 'worlds/detail' folder to 'share/scara_sim/models/detail'
        (os.path.join('share', package_name, 'models/detail'), glob('worlds/detail/*.sdf')),
        (os.path.join('share', package_name, 'models/detail'), glob('worlds/detail/*.config')),
        (os.path.join('share', package_name, 'models/detail/meshes'), glob('worlds/detail/meshes/*')),
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
        ],
    },
)
