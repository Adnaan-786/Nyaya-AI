"""One canonical form for Indian mobile numbers, used everywhere a number is stored.

This exists because of a bug worth remembering. Login normalises to `+91XXXXXXXXXX`,
but client records were storing whatever the lawyer typed. Inviting a client saved
under `9812345678` created a portal login for that string, and when the client then
signed in, the OTP flow looked up `+919812345678`, found nothing, and quietly created
a **brand-new lawyer account** for them instead of logging them into their portal.

Any two places that compare phone numbers must normalise through this function.
"""


def normalise_phone(value: str) -> str:
    """`98123 45678`, `+91-9812345678`, `919812345678` -> `+919812345678`."""
    digits = "".join(ch for ch in value if ch.isdigit())

    if len(digits) == 10:
        return f"+91{digits}"
    if len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    raise ValueError("Enter a 10-digit Indian mobile number.")
