class StatusCodeError(Exception):
    """
    Raised for unexpected or "bad" status codes.

    :param tuple expected_codes: tuple of expected codes
    :param tuple received_codes: tuple of received codes
    :param list info: list of lines with server response
    """
    def __init__(self, expected_codes, received_code, info):

        super().__init__(
            str.format(
                "Waiting for {} but got {} {}",
                expected_codes,
                received_code,
                repr(info),
            )
        )
        self.expected_codes = expected_codes
        self.received_code = received_code
        self.info = info
