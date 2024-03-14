from typing import Any, Generator, Generic, Literal, Protocol, TypeVar

from typing_extensions import TypeAlias

_T = TypeVar("_T")


class StatsProtocol(Protocol):
    @property
    def st_size(self) -> int:
        raise NotImplementedError

    @property
    def st_ctime(self) -> float:
        raise NotImplementedError

    @property
    def st_mtime(self) -> float:
        raise NotImplementedError

    @property
    def st_nlink(self) -> int:
        raise NotImplementedError

    @property
    def st_mode(self) -> int:
        raise NotImplementedError


class AsyncEnterableProtocol(Generic[_T]):
    async def __aenter__(self) -> _T:
        raise NotImplementedError

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError

    def __await__(self) -> Generator[None, None, _T]:
        raise NotImplementedError


OpenMode: TypeAlias = Literal["rb", "wb", "ab", "r+b"]
