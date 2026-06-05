from datetime import time, timezone


def get_every_hour() -> list[time]:
    return [time(hour=h, minute=0, tzinfo=timezone.utc) for h in range(24)]
