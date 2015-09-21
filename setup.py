import os
import re
from setuptools import setup, find_packages
from configparser import ConfigParser
from setuptools.command.test import test as TestCommand

config = ConfigParser(default_section='metadata', empty_lines_in_values=False)
config.read(os.path.join(os.path.dirname(__file__), 'flit.ini'))


def read(f):
    return open(os.path.join(os.path.dirname(__file__), f)).read().strip()

try:
    version = re.findall(r"""^__version__ = "([^']+)"\r?$""",
                         read(os.path.join('aioftp', '__init__.py')), re.M)[0]
except IndexError:
    raise RuntimeError('Unable to determine version.')


class NoseTestCommand(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pathlib
        import shutil
        import nose

        for path in pathlib.Path("tests").glob("*"):
            if path.is_dir():
                shutil.rmtree(str(path))

        cov = pathlib.Path(".coverage")
        if cov.exists():
            cov.unlink()

        nose.run(argv=['nosetests'])


setup(
    name=config.defaults().get('module'),
    version=version,
    description=('ftp client/server for asyncio'),
    long_description='\n\n'.join(read('readme.rst')),
    classifiers=config.defaults().get('classifiers').splitlines(),
    author=config.defaults().get('author'),
    author_email=config.defaults().get('author-email'),
    url=config.defaults().get('home-page'),
    license='Apache 2',
    packages=find_packages(),
    install_requires=[],
    tests_require=['nose', 'coverage'],
    cmdclass={'test': NoseTestCommand},
    include_package_data=True
)
