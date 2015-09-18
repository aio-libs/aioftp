import codecs
import os
import re
import sys
from setuptools import setup, find_packages, Extension
from distutils.errors import (CCompilerError, DistutilsExecError,
                              DistutilsPlatformError)
from distutils.command.build_ext import build_ext


def read(f):
    return open(os.path.join(os.path.dirname(__file__), f)).read().strip()

args = dict(
    name='aioftp',
    version='0.1.8',
    description=('ftp client/server for asyncio'),
    long_description='\n\n'.join(read('readme.rst')),
    classifiers=[
        'License :: OSI Approved :: Apache Software License',
        'Development Status :: 4 - Beta',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Topic :: Internet :: File Transfer Protocol (FTP)'],
    author='pohmelie',
    author_email='multisosnooley@gmail.com',
    url='https://github.com/pohmelie/aioftp',
    license='Apache 2',
    packages=find_packages(),
    install_requires=[],
    include_package_data=True)

setup(**args)   