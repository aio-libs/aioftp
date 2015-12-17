import os
import re
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand


def read(f):

    return open(os.path.join(os.path.dirname(__file__), f)).read().strip()

try:

    version = re.findall(r"""^__version__ = "([^']+)"\r?$""",
                         read(os.path.join("aioftp", "__init__.py")), re.M)[0]

except IndexError:

    raise RuntimeError("Unable to determine version.")


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

        nose.run(argv=["nosetests"])


setup(
    name="aioftp",
    version=version,
    description=("ftp client/server for asyncio"),
    long_description=read("readme.rst"),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Topic :: Internet :: File Transfer Protocol (FTP)",
    ],
    author="pohmelie",
    author_email="multisosnooley@gmail.com",
    url="https://github.com/pohmelie/aioftp",
    license="WTFPL",
    packages=find_packages(),
    install_requires=[],
    tests_require=["nose", "coverage"],
    cmdclass={"test": NoseTestCommand},
    include_package_data=True
)
