"""Slug utilities for generating URL-safe identifiers from org names.

Spec: REQ-SIGNUP-05
- Lowercase, hyphenated
- Dedup with -N suffix when collisions occur
"""

import re
import unicodedata


def slugify(value: str) -> str:
    """Convert a string to a URL-safe slug.

    Examples:
        "Acme Corp"    → "acme-corp"
        "Héllo Wörld"  → "hello-world"
        "foo  bar--baz"→ "foo-bar-baz"
    """
    # Normalize unicode → decompose accented chars
    value = unicodedata.normalize("NFKD", value)
    # Encode to ASCII, ignoring non-ASCII bytes
    value = value.encode("ascii", "ignore").decode("ascii")
    # Lowercase
    value = value.lower()
    # Replace non-alphanumeric chars (except hyphens) with hyphens
    value = re.sub(r"[^a-z0-9]+", "-", value)
    # Collapse multiple hyphens
    value = re.sub(r"-{2,}", "-", value)
    # Strip leading/trailing hyphens
    value = value.strip("-")
    return value or "org"


async def unique_slug(base: str, exists_fn) -> str:
    """Return a slug unique according to exists_fn(slug) → bool.

    Tries base slug first, then base-2, base-3, … until a free one is found.

    Args:
        base: The base slug (already slugified).
        exists_fn: Async callable that returns True if slug is already taken.
    """
    candidate = base
    counter = 2
    while await exists_fn(candidate):
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate
