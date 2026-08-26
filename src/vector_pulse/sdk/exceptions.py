class VectorPulseError(Exception):
    """Base exception for the VectorPulse SDK."""


class VectorPulseConnectionError(VectorPulseError):
    """Raised when the VectorPulse backend cannot be reached."""


class VectorPulseAPIError(VectorPulseError):
    """Raised when the VectorPulse API returns an error response."""

    def __init__(
        self,
        status_code: int,
        detail: str,
    ) -> None:
        self.status_code = status_code
        self.detail = detail

        super().__init__(
            f"VectorPulse API returned "
            f"{status_code}: {detail}"
        )