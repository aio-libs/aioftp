.. client_tutorial:

Client tutorial
===============

For 95% cases it is enough to use this interface methods:

.. class:: aioftp.Client

    .. coroutinefunction:: wait_for(fut, timeout, \*, loop=None)

    Wait for the single :class:`Future` or :ref:`coroutine object <coroutine>`
    to complete with timeout. If *timeout* is ``None``, block until the future
    completes.

    Coroutine will be wrapped in :class:`Task`.

    Returns result of the Future or coroutine.  When a timeout occurs, it
    cancels the task and raises :exc:`asyncio.TimeoutError`. To avoid the task
    cancellation, wrap it in :func:`shield`.

    If the wait is cancelled, the future *fut* is also cancelled.

    This function is a :ref:`coroutine <coroutine>`, usage::

        result = yield from asyncio.wait_for(fut, 60.0)

    .. versionchanged:: 3.4.3

        If the wait is cancelled, the future *fut* is now also cancelled.
