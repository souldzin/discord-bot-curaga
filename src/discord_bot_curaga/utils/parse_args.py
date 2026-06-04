import re


def parse_comma_separated_ids(raw_arg: str) -> list[int]:
    values = [item for item in re.split(r"[\s,]+", raw_arg.strip()) if item]
    result: list[int] = []

    for value in values:
        try:
            result.append(int(value))
        except ValueError:
            return []

    return result
