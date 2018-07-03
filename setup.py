import re
import pathlib
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand


BASE_PATH = pathlib.Path(__file__).parent
try:
    version = re.findall(r"""^__version__ = "([^']+)"\r?$""",
                         (BASE_PATH / "aioftp" / "__init__.py").read_text(),
                         re.M)[0]
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
        nose.main(argv=["nosetests"])


setup(
    name="aioftp",
    version=version,
    description=("ftp client/server for asyncio"),
    long_description=(BASE_PATH / "README.rst").read_text(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Topic :: Internet :: File Transfer Protocol (FTP)",
    ],
    author="pohmelie",
    author_email="multisosnooley@gmail.com",
    url="https://github.com/aio-libs/aioftp",
    license="Apache 2",
    packages=find_packages(),
    python_requires=" >= 3.5.3",
    install_requires=[],
    tests_require=["nose", "coverage"],
    cmdclass={"test": NoseTestCommand},
    include_package_data=True
)
