from setuptools import find_packages
from distutils.core import setup

setup(
    name='spindrift',
    version='1.2.2',
    packages=find_packages(exclude=['tests']),
    description='A rest framework',
    long_description="""
Documentation
-------------
    You can see the project and documentation at the `GitHub repo <https://github.com/robertchase/spindrift>`_
    """,
    author='Bob Chase',
    url='https://github.com/robertchase/spindrift',
    license='MIT',
)
