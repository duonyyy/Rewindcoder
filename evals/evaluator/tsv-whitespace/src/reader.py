import csv
from io import StringIO


def read_rows(text: str, delimiter: str) -> list[list[str]]:
    rows = list(csv.reader(StringIO(text), delimiter=delimiter))
    return rows if delimiter == "\t" else [[cell.strip() for cell in row] for row in rows]
