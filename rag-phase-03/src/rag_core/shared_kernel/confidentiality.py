"""Visibility class that controls retrieval and upward transfer."""

from enum import StrEnum


class Confidentiality(StrEnum):
    RESTRICTED = "restricted"
    INTERNAL = "internal"
    PER_ITEM = "per_item"
    PUBLIC = "public"
