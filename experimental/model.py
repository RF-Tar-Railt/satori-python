try:
    import msgspec
    from ._model_msgspec import *
except ImportError:
    from ._model_dcls import *
