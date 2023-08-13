from __future__ import annotations

from types import TracebackType
from typing import TYPE_CHECKING, Any

from aioftp import common

if TYPE_CHECKING:
    from aioftp.client import Code

__all__ = (
    "AIOFTPException",
    "NoAvailablePort",
    "PathIOError",
    "PathIsNotAbsolute",
    "StatusCodeError",
)


class AIOFTPException(Exception):
    """
    Base exception class.
    """


EXE_INFO_TYPE = tuple[type[BaseException] | None, BaseException | None, TracebackType | None]


class StatusCodeError(AIOFTPException):
    """
    Raised for unexpected or "bad" status codes.

    :param expected_codes: tuple of expected codes or expected code
    :type expected_codes: :py:class:`tuple` of :py:class:`aioftp.Code` or
        :py:class:`aioftp.Code`

    :param received_codes: tuple of received codes or received code
    :type received_codes: :py:class:`tuple` of :py:class:`aioftp.Code` or
        :py:class:`aioftp.Code`

    :param info: list of lines with server response
    :type info: :py:class:`list` of :py:class:`str`

    ::

        >>> try:
        ...     # something with aioftp
        ... except StatusCodeError as e:
        ...     print(e.expected_codes, e.received_codes, e.info)
        ...     # analyze state

    Exception members are tuples, even for one code.
    """

    def __init__(self, expected_codes: tuple[str, ...] | str, received_codes: tuple[Code, ...] | Code, info: list[str]):
        super().__init__(f"Waiting for {expected_codes} but got " f"{received_codes} {info!r}")
        self.expected_codes = common.wrap_with_container(expected_codes)
        self.received_codes = common.wrap_with_container(received_codes)
        self.info = info


class PathIsNotAbsolute(AIOFTPException):
    """
    Raised when "path" is not absolute.
    """


class PathIOError(AIOFTPException):
    """
    Universal exception for any path io errors.

    ::

        >>> try:
        ...     # some client/server path operation
        ... except PathIOError as exc:
        ...     type, value, traceback = exc.reason
        ...     if isinstance(value, SomeException):
        ...         # handle
        ...     elif ...
        ...         # handle
    """

    def __init__(self, *args: list[Any], reason: EXE_INFO_TYPE | None = None, **kwargs: dict[Any, Any]):
        super().__init__(*args, **kwargs)
        self.reason: EXE_INFO_TYPE | None = reason


class NoAvailablePort(AIOFTPException, OSError):
    """
    Raised when there is no available data port
    """
