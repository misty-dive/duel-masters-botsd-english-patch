class BotSDError(Exception):
    """Base class for BOTSD tooling errors."""


class HashMismatchError(BotSDError):
    """Raised when an input does not match an expected release hash."""


class FormatError(BotSDError):
    """Raised when a reverse-engineered binary structure is malformed."""


class VerificationError(BotSDError):
    """Raised when a generated output fails a containment or round-trip check."""
