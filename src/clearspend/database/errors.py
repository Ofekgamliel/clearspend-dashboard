class DatabaseBusyError(RuntimeError):
    """A bounded pool could not provide a connection in time."""


class DatabaseUnavailableError(RuntimeError):
    """The selected remote database cannot currently serve requests."""
