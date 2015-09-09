import logging


__all__ = ()


logger = logging.getLogger("aioftp")


def wrap_with_container(o):

    if isinstance(o, str):

        o = (o,)

    return o
