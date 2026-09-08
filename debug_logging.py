"""Shared debug logging switch for the NOD importer."""


DEBUG_LOG = False


def set_debug_logging(enabled):
    global DEBUG_LOG
    DEBUG_LOG = bool(enabled)


def debug_print(*args, **kwargs):
    if DEBUG_LOG:
        print(*args, **kwargs)
