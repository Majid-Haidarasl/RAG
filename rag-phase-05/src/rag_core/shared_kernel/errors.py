"""Domain exceptions. Application services map these to interface errors."""


class DomainError(Exception):
    """Base class for rule violations and invalid values."""


class InvariantError(DomainError):
    """An aggregate invariant was violated."""


class NotFoundError(DomainError):
    """A referenced aggregate or entity does not exist."""
