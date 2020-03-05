from . import common


__all__ = (
    "AIOFTPException",
    "StatusCodeError",
    "PathIsNotAbsolute",
    "PathIOError",
    "NoAvailablePort",
)


class AIOFTPException(Exception):
    """
    Base exception class.
    """


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
    def __init__(self, expected_codes, received_codes, info):
        super().__init__(f"Waiting for {expected_codes} but got "
                         f"{received_codes} {info!r}")
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
    def __init__(self, *args, reason=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.reason = reason


class NoAvailablePort(AIOFTPException, OSError):
    """
    Raised when there is no available data port
    """
