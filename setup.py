import os
from setuptools import setup, find_packages
from configparser import ConfigParser
from aioftp import __version__

config = ConfigParser(default_section='metadata', empty_lines_in_values=False)
config.read(os.path.join(os.path.dirname(__file__), 'flit.ini'))


def read(f):
    return open(os.path.join(os.path.dirname(__file__), f)).read().strip()

setup(
    name=config.defaults().get('module'),
    version=__version__,
    description=('ftp client/server for asyncio'),
    long_description='\n\n'.join(read('readme.rst')),
    classifiers=config.defaults().get('classifiers').splitlines(),
    author=config.defaults().get('author'),
    author_email=config.defaults().get('author-email'),
    url=config.defaults().get('home-page'),
    license='Apache 2',
    packages=find_packages(),
    install_requires=[],
    include_package_data=True
)
