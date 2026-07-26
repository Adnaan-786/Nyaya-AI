"""IST-anchored "now", mirroring `IndiaTime.kt` on the Android side.

`date.today()` returns the *server's* local date. That happens to be correct on a
developer's laptop in India and wrong on every UTC host — for five and a half hours
each night a UTC server thinks it is still yesterday. Everything this product asks
about a day ("today's hearings", the invoice date, whether a hearing is upcoming) is
a question about the day in India, so it must be answered in IST explicitly.

Nothing in `app/` should call `date.today()` or `datetime.now()` without a timezone.
"""

import datetime as dt
from zoneinfo import ZoneInfo

INDIA = ZoneInfo("Asia/Kolkata")


def now_in_india() -> dt.datetime:
    return dt.datetime.now(INDIA)


def today_in_india() -> dt.date:
    return now_in_india().date()


def to_india(moment: dt.datetime) -> dt.datetime:
    """Render a stored UTC instant in IST.

    Timestamps are stored as instants (correctly); it is only the *display* that must
    be converted. An invoice created at 04:00 UTC on the 26th was created on the 27th
    in India, and the 27th is the date that belongs on the document.
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.UTC)
    return moment.astimezone(INDIA)
