import asyncio
import logging
import re
import contextlib
import collections
import pathlib

from . import errors
from . import common


logger = logging.getLogger("aioftp")


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
        """
        Close connection.
        """
        self.writer.close()

    @asyncio.coroutine
    def parse_line(self):
        """
        :py:func:`asyncio.coroutine`

        Parsing server response line.

        :return: (code, line)
        :rtype: (:py:class:`aioftp.Code`, :py:class:`str`)
        """
        line = yield from self.reader.readline()
        s = str.rstrip(bytes.decode(line, encoding="utf-8"))
        logger.info(s)
        return common.Code(s[:3]), s[3:]

    @asyncio.coroutine
    def parse_response(self):
        """
        :py:func:`asyncio.coroutine`

        Parsing full server response (all lines).

        :return: (code, lines)
        :rtype: (:py:class:`aioftp.Code`, :py:class:`list` of :py:class:`str`)

        :raises aioftp.StatusCodeError: if received code does not matches all
            already received codes
        """
        code, rest = yield from self.parse_line()
        info = [rest]
        curr_code = code
        while str.startswith(rest, "-") or not str.isdigit(curr_code):

            curr_code, rest = yield from self.parse_line()
            if str.isdigit(curr_code):

                info.append(rest)
                if curr_code != code:

                    raise errors.StatusCodeError(code, curr_code, info)

            else:

                info.append(curr_code + rest)

        return code, info

    def check_codes(self, expected_codes, received_code, info):
        """
        Checks if any of expected matches received.

        :param expected_codes: tuple of expected codes
        :type expected_codes: :py:class:`tuple`

        :param received_code: received code for matching
        :type received_code: :py:class:`aioftp.Code`

        :param info: list of response lines from server
        :type info: :py:class:`list`

        :raises aioftp.StatusCodeError: if received code does not matches any
            expected code
        """
        if not any(map(received_code.matches, expected_codes)):

            raise errors.StatusCodeError(expected_codes, received_code, info)

    @asyncio.coroutine
    def command(self, command=None, expected_codes=(), wait_codes=()):
        """
        :py:func:`asyncio.coroutine`

        Basic command logic.

        1. Send command if not omitted.
        2. Yield response until no wait code matches.
        3. Check code for expected.

        :param command: command line
        :type command: :py:class:`str`

        :param expected_codes: tuple of expected codes
        :type expected_codes: :py:class:`tuple`

        :param wait_codes: tuple of wait codes
        :type wait_codes: :py:class:`tuple`
        """
        expected_codes = common.wrap_with_container(expected_codes)
        wait_codes = common.wrap_with_container(wait_codes)

        if command:

            logger.info(command)
            self.writer.write(str.encode(command + "\n", encoding="utf-8"))

        if expected_codes or wait_codes:

            code, info = yield from self.parse_response()
            while any(map(code.matches, wait_codes)):

                code, info = yield from self.parse_response()

            if expected_codes:

                self.check_codes(expected_codes, code, info)

            return code, info

    def parse_address_response(self, s):
        """
        Parsing ip:port server response.

        :param s: response line
        :type s: :py:class:`str`

        :return: (ip, port)
        :rtype: (:py:class:`str`, :py:class:`int`)
        """
        sub, *_ = re.findall(r"[^(]*\(([^)]*)", s)
        nums = tuple(map(int, str.split(sub, ",")))
        ip = str.join(".", map(str, nums[:4]))
        port = (nums[4] << 8) | nums[5]
        return ip, port

    def parse_directory_response(self, s):
        """
        Parsing directory server response.

        :param s: response line
        :type s: :py:class:`str`

        :rtype: :py:class:`pathlib.Path`
        """
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
        """
        Parsing MLS(T|D) response.

        :param b: response line
        :type b: :py:class:`bytes` or :py:class:`str`

        :return: (path, info)
        :rtype: (:py:class:`pathlib.Path`, :py:class:`dict`)
        """
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
    """
    FTP client.

    :param callable create_connection: factory for creating
        connection.
        Using default :py:meth:`asyncio.BaseEventLoop.create_connection`
        if omitted.
    :type create_connection: :py:func:`callable`
    """

    @asyncio.coroutine
    def connect(self, host, port=21):
        """
        :py:func:`asyncio.coroutine`

        Connect to server.

        :param str host: host name for connection
        :param int port: port number for connection
        """

        yield from super().connect(host, port)
        code, info = yield from self.command(None, "220", "120")
        return info

    @asyncio.coroutine
    def login(self, user="anonymous", password="anon@", account=""):
        """
        :py:func:`asyncio.coroutine`

        Server authentication.

        :param user: username
        :type user: :py:class:`str`

        :param password: password
        :type password: :py:class:`str`

        :param account: account (almost always blank)
        :type account: :py:class:`str`

        :raises aioftp.StatusCodeError: if unknown code received
        """
        code, info = yield from self.command("USER " + user, ("230", "33x"))
        while code.matches("33x"):

            if code == "331":

                cmd = "PASS " + password

            elif code == "332":

                cmd = "ACCT " + account

            else:

                raise errors.StatusCodeError("33x", code, info)

            code, info = yield from self.command(cmd, ("230", "33x"))

    @asyncio.coroutine
    def get_current_directory(self):
        """
        :py:func:`asyncio.coroutine`

        Getting current working directory.

        :rtype: :py:class:`pathlib.Path`
        """
        code, info = yield from self.command("PWD", "257")
        directory = self.parse_directory_response(info[-1])
        return directory

    @asyncio.coroutine
    def change_directory(self, path=".."):
        """
        :py:func:`asyncio.coroutine`

        Change current directory. Goes «up» if no parameters passed.

        :param pathlib.Path path: new directory, goes «up» if omitted
        :type path: :py:class:`str` or :py:class:`pathlib.Path`
        """
        if path in ("..", pathlib.Path("..")):

            cmd = "CDUP"

        else:

            cmd = "CWD " + str(path)

        yield from self.command(cmd, "250")

    @asyncio.coroutine
    def make_directory(self, path, *, parents=True):
        """
        :py:func:`asyncio.coroutine`

        Make directory.

        :param path: path to directory to create
        :type path: :py:class:`str` or :py:class:`pathlib.Path`

        :param parents: create parents if does not exists
        :type parents: :py:class:`bool`
        """
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
        """
        :py:func:`asyncio.coroutine`

        Low level remove method for removing empty directory.

        :param path: empty directory to remove
        :type path: :py:class:`str` or :py:class:`pathlib.Path`
        """
        yield from self.command("RMD " + str(path), "250")

    @asyncio.coroutine
    def list(self, path="", *, recursive=False, callback=None):
        """
        :py:func:`asyncio.coroutine`

        List all files and directories in "path".

        :param path: directory or file path
        :type path: :py:class:`str` or :py:class:`pathlib.Path`

        :param recursive: list recursively
        :type recursive: :py:class:`bool`

        :param callback: callback function with two arguments: path and stats
        :type callback: :py:func:`callable`

        :rtype: :py:class:`list` or :py:class:`None`
        """
        def _callback(line):

            nonlocal files
            nonlocal path
            nonlocal callback
            nonlocal directories
            name, info = self.parse_mlsx_line(line)
            if info["type"] in ("file", "dir"):

                stat = path / name, info
                if info["type"] == "dir":

                    directories.append(stat)

                if callback is None:

                    files.append(stat)

                else:

                    callback(*stat)

        files = []
        directories = []
        yield from self.retrieve(
            str.strip("MLSD " + str(path)),
            "1xx",
            use_lines=True,
            callback=_callback,
        )
        if recursive:

            deep_files = []
            for name, info in directories:

                deep_files += yield from self.list(
                    name,
                    recursive=recursive,
                    callback=callback,
                )

            files += deep_files

        return files

    @asyncio.coroutine
    def stat(self, path):
        """
        :py:func:`asyncio.coroutine`

        Getting path stats.

        :param path: path for getting info
        :type path: :py:class:`str` or :py:class:`pathlib.Path`

        :return: path info
        :rtype: :py:class:`dict`
        """
        code, info = yield from self.command("MLST " + str(path), "2xx")
        name, info = self.parse_mlsx_line(str.lstrip(info[1]))
        return info

    @asyncio.coroutine
    def is_file(self, path):
        """
        :py:func:`asyncio.coroutine`

        Checks if path is file.

        :rtype: :py:class:`bool`
        """
        info = yield from self.stat(path)
        return info["type"] == "file"

    @asyncio.coroutine
    def is_dir(self, path):
        """
        :py:func:`asyncio.coroutine`

        Checks if path is dir.

        :rtype: :py:class:`bool`
        """
        info = yield from self.stat(path)
        return info["type"] == "dir"

    @asyncio.coroutine
    def exists(self, path):
        """
        :py:func:`asyncio.coroutine`

        Check path for existence.

        :param path: path for checking on server side
        :type path: :py:class:`str` or :py:class:`pathlib.Path`

        :rtype: :py:class:`bool`
        """
        code, info = yield from self.command(
            "MLST " + str(path),
            ("2xx", "550")
        )
        exists = code.matches("2xx")
        return exists

    @asyncio.coroutine
    def rename(self, source, destination):
        """
        :py:func:`asyncio.coroutine`

        Rename (move) file or directory.

        :param source: path to rename
        :type source: :py:class:`str` or :py:class:`pathlib.Path`

        :param destination: path new name
        :type destination: :py:class:`str` or :py:class:`pathlib.Path`
        """
        yield from self.command("RNFR " + str(source), "350")
        yield from self.command("RNTO " + str(destination), "2xx")

    @asyncio.coroutine
    def remove_file(self, path):
        """
        :py:func:`asyncio.coroutine`

        Low level remove method for removing file.

        :param path: file to remove
        :type path: :py:class:`str` or :py:class:`pathlib.Path`
        """
        yield from self.command("DELE " + str(path), "2xx")

    @asyncio.coroutine
    def remove(self, path):
        """
        :py:func:`asyncio.coroutine`

        High level remove method for removing path recursively (file or
        directory).

        :param path: path to remove
        :type path: :py:class:`str` or :py:class:`pathlib.Path`
        """
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
    def upload_file(self, destination, file, *, callback=None,
                    block_size=8192):
        """
        :py:func:`asyncio.coroutine`

        Low level upload method for uploading file from file-like object.

        :param destination: destination path of file or directory on server
            side
        :type destination: :py:class:`str` or :py:class:`pathlib.Path`

        :param file: file-like object for reading data (providing read method)

        :param callback: callback function with one argument — sended
            :py:class:`bytes` to server.
        :type callback: :py:func:`callable`

        :param block_size: block size for transaction
        :type block_size: :py:class:`int`
        """
        yield from self.store(
            "STOR " + str(destination),
            "1xx",
            file=file,
            callback=callback,
            block_size=block_size,
        )

    @asyncio.coroutine
    def upload(self, source, destination="", *, write_into=False,
               callback=None, block_size=8192):
        """
        :py:func:`asyncio.coroutine`

        High level upload method for uploading files and directories
        recursively from file system.

        :param source: source path of file or directory on client side
        :type source: :py:class:`str` or :py:class:`pathlib.Path`

        :param destination: destination path of file or directory on server
            side
        :type destination: :py:class:`str` or :py:class:`pathlib.Path`

        :param write_into: write source into destination (if you want upload
            file and change it name, as well with directories)
        :type write_into: :py:class:`bool`

        :param callback: callback function with one argument — sended
            :py:class:`bytes` to server. This one should be used only for
            progress view, cause there is no information about which file this
            bytes really belongs.
        :type callback: :py:func:`callable`

        :param block_size: block size for transaction
        :type block_size: :py:class:`int`
        """
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
    def download_file(self, source, *, callback, block_size=8192):
        """
        :py:func:`asyncio.coroutine`

        Low level download method for downloading file without saving.

        :param source: source path of file or directory on server side
        :type source: :py:class:`str` or :py:class:`pathlib.Path`

        :param callback: callback function with one argument — received
            :py:class:`bytes` from server.
        :type callback: :py:func:`callable`

        :param block_size: block size for transaction
        :type block_size: :py:class:`int`
        """
        yield from self.retrieve(
            "RETR " + str(source),
            "1xx",
            callback=callback,
            block_size=block_size,
        )

    @asyncio.coroutine
    def download(self, source, destination="", *, write_into=False,
                 callback=None, block_size=8192):
        """
        :py:func:`asyncio.coroutine`

        High level download method for downloading files and directories
        recursively and save them to the file system.

        :param source: source path of file or directory on server side
        :type source: :py:class:`str` or :py:class:`pathlib.Path`

        :param destination: destination path of file or directory on client
            side
        :type destination: :py:class:`str` or :py:class:`pathlib.Path`

        :param write_into: write source into destination (if you want download
            file and change it name, as well with directories)
        :type write_into: :py:class:`bool`

        :param callback: callback function with one argument — received
            :py:class:`bytes` from server. This one should be used only for
            progress view, cause there is no information about which file this
            bytes really belongs.
        :type callback: :py:func:`callable`

        :param block_size: block size for transaction
        :type block_size: :py:class:`int`
        """
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
        """
        :py:func:`asyncio.coroutine`

        Send "QUIT" and close connection.
        """
        yield from self.command("QUIT", "2xx")
        self.close()

    @asyncio.coroutine
    def get_passive_connection(self, conn_type="I"):
        """
        :py:func:`asyncio.coroutine`

        Getting pair of reader, writer for passive connection with server.

        :param conn_type: connection type ("I", "A", "E", "L")
        :type conn_type: :py:class:`str`

        :rtype: (:py:class:`asyncio.StreamReader`,
            :py:class:`asyncio.StreamWriter`)
        """
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
    def retrieve(self, *command_args, conn_type="I", use_lines=False,
                 callback=None, block_size=8192):
        """
        :py:func:`asyncio.coroutine`

        Retrieve data from passive connection with some command

        :param command_args: arguments for :py:meth:`aioftp.Client.command`

        :param conn_type: connection type ("I", "A", "E", "L")
        :type conn_type: :py:class:`str`

        :param use_lines: use lines or block size for read
        :type use_lines: :py:class:`bool`

        :param callback: callback function with one argument — received
            :py:class:`bytes` from server.
        :type callback: :py:func:`callable`

        :param block_size: block size for transaction
        :type block_size: :py:class:`int`
        """
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
    def store(self, *command_args, file, conn_type="I", use_lines=False,
              callback=None, block_size=8192):
        """
        :py:func:`asyncio.coroutine`

        Store data to passive connection with some command

        :param command_args: arguments for :py:meth:`aioftp.Client.command`

        :param file: file-like object for reading data (providing read method)

        :param conn_type: connection type ("I", "A", "E", "L")
        :type conn_type: :py:class:`str`

        :param use_lines: use lines or block size for write
        :type use_lines: :py:class:`bool`

        :param callback: callback function with one argument — sended
            :py:class:`bytes` to server.
        :type callback: :py:func:`callable`

        :param block_size: block size for transaction
        :type block_size: :py:class:`int`
        """
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
