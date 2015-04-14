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


FileInfo = collections.namedtuple("FileInfo", "name info")


@asyncio.coroutine
def open_connection(host, port, create_connection=None):

    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader(loop=loop)
    protocol = asyncio.StreamReaderProtocol(reader, loop=loop)
    create_connection = create_connection or loop.create_connection
    transport, _ = yield from create_connection(lambda: protocol, host, port)
    writer = asyncio.StreamWriter(transport, protocol, reader, loop)
    return reader, writer


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

        return directory

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

        return FileInfo(name, entry)


class Client(BaseClient):

    @asyncio.coroutine
    def connect(self, host, port=21):

        yield from super().connect(host, port)
        code, info = yield from self.command(None, "220", "120")
        return code, info

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

        return code, info

    @asyncio.coroutine
    def get_current_directory(self):

        code, info = yield from self.command("PWD", "257")
        directory = self.parse_directory_response(info[-1])
        return directory

    @asyncio.coroutine
    def change_directory(self, path=None):

        if path:

            cmd = "CWD " + path

        else:

            cmd = "CDUP"

        yield from self.command(cmd, "250")

    @asyncio.coroutine
    def make_directory(self, path):

        code, info = yield from self.command("MKD " + path, "257")
        directory = self.parse_directory_response(info[-1])
        return directory

    @asyncio.coroutine
    def remove_directory(self, path):

        yield from self.command("RMD " + path, "250")

    @asyncio.coroutine
    def list_directory(self, path=""):

        lines = []
        yield from self.retrieve(
            str.strip("MLSD " + path),
            "1xx",
            use_lines=True,
            callback=lines.append,
        )
        info = tuple(map(self.parse_mlsx_line, lines))
        return info

    @asyncio.coroutine
    def path_info(self, path):

        code, info = yield from self.command("MLST " + path, "2xx")
        info = self.parse_mlsx_line(str.lstrip(info[1]))
        return info

    @asyncio.coroutine
    def path_exist(self, path):

        code, info = yield from self.command("MLST " + path, ("2xx", "550"))
        exist = code.matches("2xx")
        return exist

    @asyncio.coroutine
    def move_file(self, src, dst):

        code, info = yield from self.command("RNFR " + src, "350")
        code, info = yield from self.command("RNTO " + dst, "2xx")
        return code, info

    @asyncio.coroutine
    def remove_file(self, path):

        code, info = yield from self.command("DELE " + path, "2xx")
        return code, info

    @asyncio.coroutine
    def remove_recursive(self, path):

        info = yield from self.path_info(path)
        if info.info["type"] == "file":

            yield from self.remove_file(path)

        elif info.info["type"] == "dir":

            sub_dir = yield from self.list_directory(path)
            for sub_dir_info in sub_dir:

                if sub_dir_info.info["type"] in ("dir", "file"):

                    npath = pathlib.Path(path) / sub_dir_info.name
                    yield from self.remove_recursive(str(npath))

            yield from self.remove_directory(path)

    @asyncio.coroutine
    def upload_file(self, path, file, *, callback=None, block_size=8192):

        yield from self.store(
            "STOR " + path,
            "1xx",
            file=file,
            callback=callback,
            block_size=block_size,
        )

    @asyncio.coroutine
    def download_file(self, path, *, callback, block_size=8192):

        yield from self.retrieve(
            "RETR " + path,
            "1xx",
            callback=callback,
            block_size=block_size,
        )

    @asyncio.coroutine
    def quit(self):

        code, info = yield from self.command("QUIT", "2xx")
        return code, info

    @asyncio.coroutine
    def get_passive_connection(self, conn_type="I"):

        yield from self.command("TYPE " + conn_type, "200")
        code, info = yield from self.command("PASV", "227")
        ip, port = self.parse_address_response(info[-1])
        reader, writer = yield from open_connection(
            ip,
            port,
            self.create_connection
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
