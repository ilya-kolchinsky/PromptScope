"""
Exception hierarchy for PromptScope.

All PromptScope exceptions inherit from PromptScopeError.
"""


class PromptScopeError(Exception):
    """Base exception for all PromptScope errors."""
    pass


class ConfigurationError(PromptScopeError):
    """Raised when there is a configuration problem."""
    pass


class ValidationError(PromptScopeError):
    """Raised when input validation fails."""
    pass


class SecurityError(PromptScopeError):
    """
    Raised when a security-critical operation fails.

    This is a fail-fast exception to prevent unprotected requests from
    reaching the LLM when protection is expected.
    """
    pass


class NotFoundError(PromptScopeError):
    """Raised when a requested resource (message, user, etc.) is not found."""
    pass


class PermissionError(PromptScopeError):
    """Raised when a user lacks required permissions."""
    pass


class SerializationError(PromptScopeError):
    """Raised when serialization or deserialization fails."""
    pass
