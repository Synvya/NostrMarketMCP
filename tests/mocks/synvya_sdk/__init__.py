"""Mock synvya_sdk module."""

from .nostr import (
    Namespace,
    NostrClient,
    NostrKeys,
    Profile,
    ProfileFilter,
    ProfileType,
    generate_keys,
)

__all__ = [
    "Namespace",
    "NostrClient",
    "NostrKeys",
    "Profile",
    "ProfileFilter",
    "ProfileType",
    "generate_keys",
]
