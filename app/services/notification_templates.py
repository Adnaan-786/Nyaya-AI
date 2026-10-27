"""
Push copy (English + Hindi) and the deep-link scheme from contract B.8.
Kept deliberately simple string templates -- the app team can iterate
on wording without touching the dispatch logic in
notification_dispatch_service.py.
"""


def deep_link_for(notification_type: str, data: dict) -> str:
    """Contract B.8 deep-link scheme table."""
    if notification_type in ("hearing_reminder", "case_update"):
        return f"nyayaai://case/{data['case_id']}"
    if notification_type == "daily_digest":
        return "nyayaai://today"
    if notification_type == "ai_job_complete":
        return f"nyayaai://job/{data['job_id']}"
    if notification_type == "payment_received":
        return f"nyayaai://invoice/{data['invoice_id']}"
    if notification_type == "task_assigned":
        return f"nyayaai://task/{data['task_id']}"
    return "nyayaai://today"


def hearing_reminder_copy(*, case_title: str, hearing_date: str, language: str) -> tuple[str, str]:
    if language == "hi":
        return (
            "Aaj peshi hai",
            f"{case_title} mein aaj ({hearing_date}) peshi hai.",
        )
    return ("Hearing today", f"You have a hearing today ({hearing_date}) for {case_title}.")


def daily_digest_copy(*, hearing_count: int, language: str) -> tuple[str, str]:
    if language == "hi":
        return (
            "Kal ki peshiyaan",
            f"Kal aapki {hearing_count} peshiyaan hain.",
        )
    return (
        "Tomorrow's hearings",
        f"You have {hearing_count} hearing(s) scheduled tomorrow.",
    )


def case_update_copy(*, change_summary: str, language: str) -> tuple[str, str]:
    if language == "hi":
        return ("Case update", f"Aapke case mein update hai: {change_summary}")
    return ("Case update", change_summary)


def ai_job_complete_copy(*, job_type: str, language: str) -> tuple[str, str]:
    if language == "hi":
        return ("AI kaam poora hua", f"Aapka {job_type} tayyar hai.")
    return ("AI job complete", f"Your {job_type} is ready to view.")


def task_assigned_copy(*, task_title: str, language: str) -> tuple[str, str]:
    if language == "hi":
        return ("Naya kaam saunpa gaya", f"Aapko yeh kaam saunpa gaya hai: {task_title}")
    return ("New task assigned", f"You've been assigned: {task_title}")


def payment_received_copy(*, amount_paise: int, language: str) -> tuple[str, str]:
    amount_rupees = amount_paise / 100
    if language == "hi":
        return ("Bhugtan mila", f"Rs. {amount_rupees:,.2f} ka bhugtan mila hai.")
    return ("Payment received", f"A payment of Rs. {amount_rupees:,.2f} has been received.")


def outcome_nudge_copy(*, case_title: str, language: str) -> tuple[str, str]:
    """
    Plan C.10: "hearing-outcome nudge the evening after a hearing
    ('Update outcome for …')." Not a distinct contract B.8 push type --
    reuses "hearing_reminder" with a payload marker, since B.8's fixed
    type list doesn't include a separate one (see notification_worker.py).
    """
    if language == "hi":
        return ("Peshi ka result update karein", f"{case_title} ke liye result update karein.")
    return ("Update outcome for hearing", f"Please update the outcome for {case_title}.")
