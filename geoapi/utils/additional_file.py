from dataclasses import dataclass


@dataclass
class AdditionalFile:
    """Represents an additional file with its path and if its required (i.e. not optional)."""

    path: str
    required: bool
