from setuptools import setup, find_packages
import os

version = '3.9.0'


DESCRIPTION = open(
    os.path.join(os.path.dirname(__file__), 'README.txt')
    ).read() + """

A `development version`_ is available.

.. _development version:
   http://github.com/11craft/duruses/zipball/master#egg=duruses-dev
"""


setup(
    name='duruses',
    version=version,
    description="Durus Extended Server",
    long_description=DESCRIPTION,
    classifiers=[],
    keywords='',
    author='ElevenCraft Inc.',
    author_email='matt@11craft.com',
    url='http://11craft.github.com/duruses/',
    license='MIT',
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    include_package_data=True,
    zip_safe=False,
    install_requires = [
        'argparse >= 1.0.1',
        'cogen >= 0.2.1, < 0.3',
        'Durus >= 3.9, < 4.0',
        ],
    dependency_links = [
        'http://schevo.org/eggs/',
        ],
    entry_points="""
    [console_scripts]
    duruses-server = duruses.server:main
    duruses-client = duruses.client:main
    """,
    )
