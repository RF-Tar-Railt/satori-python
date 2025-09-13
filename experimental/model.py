from importlib.util import find_spec

if find_spec("msgspec") is not None:
    from ._model_msgspec import *  # noqa: F403,F401
else:
    from ._model_dcls import *  # noqa: F403,F401
