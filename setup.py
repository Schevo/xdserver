from setuptools import setup, find_packages
import sys, os

version = '3.9a1'

setup(
    name='duruses',
    version=version,
    description="Durus Extended Server",
    long_description="""\
    """,
    classifiers=[],
    keywords='',
    author='ElevenCraft Inc.',
    author_email='matt@11craft.com',
    url='',
    license='MIT',
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'Durus >= 3.9, < 4.0',
    ],
    entry_points="""
    """,
)
