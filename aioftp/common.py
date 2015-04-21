class Code(str):
    """
    Representation of server status code.
    """
    def matches(self, mask):
        """
        :param str mask: Template for comparision. If mask symbol is not digit
            then it passes.

        Usage::

            >>> Code("123").matches("1")
            True
            >>> Code("123").matches("1*3")
            True
        """
        return all(map(lambda m, c: not str.isdigit(m) or m == c, mask, self))
