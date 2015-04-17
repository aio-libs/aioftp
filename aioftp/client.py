import asyncio
import logging
import re
import contextlib
import collections
import pathlib


logger = logging.getLogger("aioftp")


class StatusCodeError(Exception):

    def __init__(self, expect_codes, received_code, info):

        super().__init__(
            str.format(
                "Waiting for {} but got {} {}",
                expect_codes,
                received_code,
                repr(info),
            )
        )
        self.expect_codes = expect_codes
        self.received_code = received_code
        self.info = info


class Code(str):

    def matches(self, mask):

        return all(map(lambda m, c: not str.isdigit(m) or m == c, mask, self))


@asyncio.coroutine
def open_connection(host, port, create_connection=None):

    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader(loop=loop)
    protocol = asyncio.StreamReaderProtocol(reader, loop=loop)
    create_connection = create_connection or loop.create_connection
    transport, _ = yield from create_connection(lambda: protocol, host, port)
    writer = asyncio.StreamWriter(transport, protocol, reader, loop)
    return reader, writer


def ChainCallback(*callbacks):

    def callback(*args, **kwargs):

        for f in callbacks:

            if f:

                f(*args, **kwargs)

    return callback


class BaseClient:

    def __init__(self, create_connection=None):

        self.create_connection = create_connection

    @asyncio.coroutine
    def connect(self, host, port=21):

        self.reader, self.writer = yield from open_connection(
            host,
            port,
            self.create_connection
        )

    def close(self):

        self.writer.close()

    @asyncio.coroutine
    def parse_line(self):

        line = yield from self.reader.readline()
        s = str.rstrip(bytes.decode(line, encoding="utf-8"))
        logger.info(s)
        return Code(s[:3]), s[3:]

    @asyncio.coroutine
    def parse_response(self):

        code, rest = yield from self.parse_line()
        info = [rest]
        curr_code = code
        while str.startswith(rest, "-") or not str.isdigit(curr_code):

            curr_code, rest = yield from self.parse_line()
            if str.isdigit(curr_code):

                info.append(rest)
                if curr_code != code:

                    raise StatusCodeError(code, curr_code, info)

            else:

                info.append(curr_code + rest)

        return code, info

    def check_codes(self, expect_codes, received_code, info):

        if not any(map(received_code.matches, expect_codes)):

            raise StatusCodeError(expect_codes, received_code, info)

    def wrap_with_container(self, o):

        if isinstance(o, str):

            o = (o,)

        return o

    @asyncio.coroutine
    def command(self, command=None, expect_codes=(), wait_codes=()):

        expect_codes = self.wrap_with_container(expect_codes)
        wait_codes = self.wrap_with_container(wait_codes)

        if command:

            logger.info(command)
            self.writer.write(str.encode(command + "\n", encoding="utf-8"))

        if expect_codes or wait_codes:

            code, info = yield from self.parse_response()
            while any(map(code.matches, wait_codes)):

                code, info = yield from self.parse_response()

            if expect_codes:

                self.check_codes(expect_codes, code, info)

            return code, info

    def parse_address_response(self, s):

        sub, *_ = re.findall(r"[^(]*\(([^)]*)", s)
        nums = tuple(map(int, str.split(sub, ",")))
        ip = str.join(".", map(str, nums[:4]))
        port = (nums[4] << 8) | nums[5]
        return ip, port

    def parse_directory_response(self, s):

        seq_quotes = 0
        start = False
        directory = ""
        for ch in s:

            if not start:

                if ch == '"':

                    start = True

            else:

                if ch == '"':

                    seq_quotes += 1

                else:

                    if seq_quotes == 1:

                        break

                    elif seq_quotes == 2:

                        seq_quotes = 0
                        directory += '"'

                    directory += ch

        return pathlib.Path(directory)

    def parse_mlsx_line(self, b):

        if isinstance(b, bytes):

            s = str.rstrip(bytes.decode(b, encoding="utf-8"))

        else:

            s = b

        line = str.rstrip(s, "\n")
        facts_found, _, name = str.partition(line, " ")
        entry = {}
        for fact in str.split(facts_found[:-1], ";"):

            key, _, value = str.partition(fact, "=")
            entry[key.lower()] = value

        return pathlib.Path(name), entry


class Client(BaseClient):

    @asyncio.coroutine
    def connect(self, host, port=21):

        yield from super().connect(host, port)
        code, info = yield from self.command(None, "220", "120")
        return info

    @asyncio.coroutine
    def login(self, user="anonymous", password="anon@", account=""):

        code, info = yield from self.command("USER " + user, ("230", "33x"))
        while code.matches("33x"):

            if code == "331":

                cmd = "PASS " + password

            elif code == "332":

                cmd = "ACCT " + account

            else:

                raise StatusCodeError("33x", code, info)

            code, info = yield from self.command(cmd, ("230", "33x"))

    @asyncio.coroutine
    def get_current_directory(self):

        code, info = yield from self.command("PWD", "257")
        directory = self.parse_directory_response(info[-1])
        return directory

    @asyncio.coroutine
    def change_directory(self, path=".."):

        if path in ("..", pathlib.Path("..")):

            cmd = "CDUP"

        else:

            cmd = "CWD " + str(path)

        yield from self.command(cmd, "250")

    @asyncio.coroutine
    def make_directory(self, path, parents=True):

        path = pathlib.Path(path)
        need_create = []
        while path.name and not (yield from self.exists(path)):

            need_create.append(path)
            path = path.parent
            if not parents:

                break

        need_create.reverse()
        for path in need_create:

            code, info = yield from self.command("MKD " + str(path), "257")
            directory = self.parse_directory_response(info[-1])

    @asyncio.coroutine
    def remove_directory(self, path):

        yield from self.command("RMD " + str(path), "250")

    @asyncio.coroutine
    def list(self, path="", *, recursive=False):

        def callback(line):

            nonlocal files
            nonlocal path
            name, info = self.parse_mlsx_line(line)
            if info["type"] in ("file", "dir"):

                files.append((path / name, info))

        files = []
        yield from self.retrieve(
            str.strip("MLSD " + str(path)),
            "1xx",
            use_lines=True,
            callback=callback,
        )
        if recursive:

            deep_files = []
            for name, info in files:

                if info["type"] == "dir":

                    deep_files += yield from self.list(
                        name,
                        recursive=recursive,
                    )

            files += deep_files

        return files

    @asyncio.coroutine
    def stat(self, path):

        code, info = yield from self.command("MLST " + str(path), "2xx")
        name, info = self.parse_mlsx_line(str.lstrip(info[1]))
        return info

    @asyncio.coroutine
    def is_file(self, path):

        info = yield from self.stat(path)
        return info["type"] == "file"

    @asyncio.coroutine
    def is_dir(self, path):

        info = yield from self.stat(path)
        return info["type"] == "dir"

    @asyncio.coroutine
    def exists(self, path):

        code, info = yield from self.command(
            "MLST " + str(path),
            ("2xx", "550")
        )
        exists = code.matches("2xx")
        return exists

    @asyncio.coroutine
    def rename(self, source, destination):

        yield from self.command("RNFR " + str(source), "350")
        yield from self.command("RNTO " + str(destination), "2xx")

    @asyncio.coroutine
    def remove_file(self, path):

        yield from self.command("DELE " + str(path), "2xx")

    @asyncio.coroutine
    def remove(self, path):

        if (yield from self.exists(path)):

            info = yield from self.stat(path)
            if info["type"] == "file":

                yield from self.remove_file(path)

            elif info["type"] == "dir":

                for name, info in (yield from self.list(path)):

                    if info["type"] in ("dir", "file"):

                        yield from self.remove(name)

                yield from self.remove_directory(path)

    @asyncio.coroutine
    def upload_file(self, path, file, *, callback=None, block_size=8192):

        yield from self.store(
            "STOR " + str(path),
            "1xx",
            file=file,
            callback=callback,
            block_size=block_size,
        )

    @asyncio.coroutine
    def upload(self, source, destination="", *, write_into=False,
               callback=None, block_size=8192):

        source = pathlib.Path(source)
        destination = pathlib.Path(destination)
        if not write_into:

            destination = destination / source.name

        if source.is_file():

            yield from self.make_directory(destination.parent)
            with source.open(mode="rb") as fin:

                yield from self.upload_file(
                    destination,
                    fin,
                    callback=callback,
                    block_size=block_size,
                )

        elif source.is_dir():

            yield from self.make_directory(destination)
            for p in source.rglob("*"):

                if write_into:

                    relative = destination.name / p.relative_to(source)

                else:

                    relative = p.relative_to(source.parent)

                if p.is_dir():

                    yield from self.make_directory(relative)

                else:

                    yield from self.make_directory(relative.parent)
                    with p.open(mode="rb") as fin:

                        yield from self.upload_file(
                            relative,
                            fin,
                            callback=callback,
                            block_size=block_size,
                        )

    @asyncio.coroutine
    def download_file(self, path, *, callback, block_size=8192):

        yield from self.retrieve(
            "RETR " + str(path),
            "1xx",
            callback=callback,
            block_size=block_size,
        )

    @asyncio.coroutine
    def download(self, source, destination="", *, write_into=False,
                 callback=None, block_size=8192):

        source = pathlib.Path(source)
        destination = pathlib.Path(destination)
        if not write_into:

            destination = destination / source.name

        if (yield from self.is_file(source)):

            if not destination.parent.exists():

                destination.parent.mkdir()

            with destination.open(mode="wb") as fout:

                yield from self.download_file(
                    source,
                    callback=ChainCallback(fout.write, callback),
                    block_size=block_size,
                )

        elif (yield from self.is_dir(source)):

            if not destination.exists():

                destination.mkdir(parents=True)

            for name, info in (yield from self.list(source, recursive=True)):

                full = destination / name.relative_to(source)
                if info["type"] == "file":

                    if not full.parent.exists():

                        full.parent.mkdir(parents=True)

                    with full.open(mode="wb") as fout:

                        yield from self.download_file(
                            name,
                            callback=ChainCallback(fout.write, callback),
                            block_size=block_size,
                        )

                elif info["type"] == "dir":

                    if not full.exists():

                        full.mkdir(parents=True)

    @asyncio.coroutine
    def quit(self):

        yield from self.command("QUIT", "2xx")
        self.close()

    @asyncio.coroutine
    def get_passive_connection(self, conn_type="I"):

        yield from self.command("TYPE " + conn_type, "200")
        code, info = yield from self.command("PASV", "227")
        ip, port = self.parse_address_response(info[-1])
        reader, writer = yield from open_connection(
            ip,
            port,
            self.create_connection,
        )
        return reader, writer

    @asyncio.coroutine
    def retrieve(self, *command_args, conn_type="I", block_size=8192,
                 use_lines=False, callback=None):

        reader, writer = yield from self.get_passive_connection(conn_type)
        yield from self.command(*command_args)
        with contextlib.closing(writer) as writer:

            while True:

                if use_lines:

                    block = yield from reader.readline()

                else:

                    block = yield from reader.read(block_size)

                if not block:

                    break

                if callback:

                    callback(block)

        yield from self.command(None, "2xx")

    @asyncio.coroutine
    def store(self, *command_args, file, conn_type="I", block_size=8192,
              use_lines=False, callback=None):

        reader, writer = yield from self.get_passive_connection(conn_type)
        yield from self.command(*command_args)
        with contextlib.closing(writer) as writer:

            while True:

                if use_lines:

                    block = file.readline()

                else:

                    block = file.read(block_size)

                if not block:

                    break

                writer.write(block)
                yield from writer.drain()

                if callback:

                    callback(block)

        yield from self.command(None, "2xx")
