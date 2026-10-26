from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> str:
    return datetime.now(IST).isoformat()


def today_ist() -> str:
    return datetime.now(IST).date().isoformat()
