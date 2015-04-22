from . import common


class StatusCodeError(Exception):
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

    Usage::

        >>> try:
        ...     # something with aioftp
        ... except StatusCodeError as e:
        ...     print(e.expected_codes, e.received_codes, e.info)
        ...     # analyze state

    Exception members are tuples, even for one code.
    """
    def __init__(self, expected_codes, received_codes, info):

        super().__init__(
            str.format(
                "Waiting for {} but got {} {}",
                expected_codes,
                received_codes,
                repr(info),
            )
        )
        self.expected_codes = common.wrap_with_container(expected_codes)
        self.received_codes = common.wrap_with_container(received_codes)
        self.info = info
