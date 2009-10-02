from setuptools import setup, find_packages
import os

version = '3.9.1'


DESCRIPTION = open(
    os.path.join(os.path.dirname(__file__), 'README.txt')
    ).read() + """

A `development version`_ is available.

.. _development version:
   http://github.com/11craft/xdserver/zipball/master#egg=xdserver-dev
"""


setup(
    name='xdserver',
    version=version,
    description="Extended Durus Server",
    long_description=DESCRIPTION,
    classifiers=[],
    keywords='',
    author='ElevenCraft Inc.',
    author_email='matt@11craft.com',
    url='http://11craft.github.com/xdserver/',
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
    xdserver = xdserver.server:main
    xdclient = xdserver.client:main
    """,
    )
