def parse_name(value: str) -> str:
    """Return a normalized name or reject an empty one."""
    name = value.strip()
    if not name:
        raise ValueError("name must not be empty")
    return name
