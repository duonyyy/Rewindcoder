from src.adapter import normalize_amount


def invoice_total(values: list[int]) -> int:
    return sum(normalize_amount(value) for value in values)
