import importlib


def import_by_pathname(target):
    if isinstance(target, str):
        modnam, funnam = target.rsplit('.', 1)
        mod = importlib.import_module(modnam)
        return getattr(mod, funnam)
    return target
