"""Project-specific errors used at module boundaries."""


class MultisubsError(Exception):
    """Base class for user-actionable multisubs failures."""


class ValidationError(MultisubsError):
    """Raised when user input cannot satisfy the project contract."""


class TemplateError(MultisubsError):
    """Raised when packaged subtitle template resources are invalid."""


class DependencyError(MultisubsError):
    """Raised when a required executable or Python package is unavailable."""


class TranscriptionError(MultisubsError):
    """Raised when model loading, transcription, or alignment fails."""


class ArtifactError(MultisubsError):
    """Raised when an artifact cannot be serialized, written, or published."""


class RenderingError(MultisubsError):
    """Raised when FFmpeg cannot render the subtitle-burned video."""
