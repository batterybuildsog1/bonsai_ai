class BonsaiAIError(Exception):
    """Base error for the Bonsai AI integration."""


class ProviderError(BonsaiAIError):
    """Raised when an upstream model call fails or returns invalid data."""


class ValidationError(BonsaiAIError):
    """Raised when a generated action plan is malformed."""

