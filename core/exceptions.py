"""Custom exceptions for P2P Trade Platform."""


class InsufficientBalanceError(Exception):
    """Raised when user's wallet balance is insufficient for operation."""
    pass


class AccountLockedException(Exception):
    """Raised when account is locked due to failed login attempts."""
    pass


class InvalidTransactionError(Exception):
    """Raised when transaction parameters are invalid."""
    pass


class DealExpiredError(Exception):
    """Raised when attempting to accept an expired deal."""
    pass


class DisputeResolutionError(Exception):
    """Raised when dispute resolution fails."""
    pass

