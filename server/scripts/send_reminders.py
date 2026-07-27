"""Cron entrypoint for hearing reminders (B.8).

    0 18 * * *  cd /srv/nyayaai && ./.venv/bin/python -m scripts.send_reminders

18:00 IST — the evening before, while a lawyer can still prepare. Safe to run more
often than needed: `send_hearing_reminders` will not notify the same person about the
same hearing twice.
"""

import asyncio
import logging

from app.core.db import SessionFactory
from app.services.reminders import send_hearing_reminders

logging.basicConfig(level=logging.INFO, format="%(message)s")


async def main() -> None:
    async with SessionFactory() as session:
        await send_hearing_reminders(session)


if __name__ == "__main__":
    asyncio.run(main())
