import sh
import pathlib
import os
import aioftp
import inspect


for path in pathlib.Path("tests").glob("*"):

    if path.is_dir():

        sh.rm("-rdf", str(path))

cov = pathlib.Path(".coverage")
if cov.exists():

    cov.unlink()

run_tests = sh.Command("nosetests")
for el in dir(aioftp):

    item = getattr(aioftp, el)
    if inspect.isclass(item) and issubclass(item, aioftp.AbstractPathIO) and \
       item is not aioftp.AbstractPathIO:

        print(str.format("Testing {}", el))
        new_env = os.environ.copy()
        new_env["AIOFTP_TESTS"] = el
        p = run_tests(
            str.format("--exclude={}", __file__),
            "--stop",
            "--no-byte-compile",
            "--with-coverage",
            "--cover-package=aioftp",
            "--logging-format='%(asctime)s %(message)s'",
            "--logging-datefmt='[%H:%M:%S]:'",
            "--logging-level=INFO",
            _env=new_env,
            _err=lambda line: print(str.strip(line)),
            _out=lambda line: print(str.strip(line)),
        )
