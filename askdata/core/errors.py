"""Defines the small set of application errors shared across backend modules."""


class AppError(Exception):
    """Represents an expected application error that can be returned to API clients."""


class DataError(AppError):
    """Represents a BIRD data loading or preparation error."""


class SqlError(AppError):
    """Represents a SQL validation, generation, or execution error."""


class ModelError(AppError):
    """Represents an external model call error."""
