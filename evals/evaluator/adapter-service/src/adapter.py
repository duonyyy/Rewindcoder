def normalize_amount(value: int) -> int:
    if value < 0:
        raise ValueError("negative amount")
    return value
