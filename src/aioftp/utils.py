from typing import Any, Dict, Tuple


def get_param(where: Tuple[int, str], args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> Any:
    return kwargs.get(where[1]) or args[where[0]]
