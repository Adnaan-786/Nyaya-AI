"""The C.9 draftsman catalogue: each template is a typed field schema plus drafting
instructions for the model.

The split matters. Fields are what the app renders as a form and what
`draft_service.compute_missing_fields` reports on; instructions are the only thing the
model is told about how the document should read. Facts come from fields, prose comes
from instructions, and nothing comes from the model's imagination — a missing field is
reported as missing rather than quietly filled with something plausible.

Money fields are integer paise, like every other amount in this server, and date fields
are dates. The app renders them from `type`, so a rupee-denominated field here would
show up as a hundred-fold error on a legal notice.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TemplateField:
    name: str
    label: str
    # string | date | number | text (multi-line)
    type: str = "string"
    required: bool = True


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    category: str
    fields: list[TemplateField]
    instructions: str


TEMPLATES: dict[str, Template] = {
    "bail_application": Template(
        id="bail_application",
        name="Bail Application (Section 437/439 BNSS)",
        category="criminal",
        fields=[
            TemplateField("court_name", "Court name"),
            TemplateField("case_number", "Case / FIR number"),
            TemplateField("police_station", "Police station"),
            TemplateField("accused_name", "Accused name"),
            TemplateField("sections_invoked", "Sections invoked"),
            TemplateField("date_of_arrest", "Date of arrest", type="date"),
            TemplateField("grounds_for_bail", "Grounds for bail", type="text"),
            TemplateField("surety_details", "Surety details", type="text", required=False),
        ],
        instructions=(
            "Draft a bail application under Section 437/439 BNSS. Structure: "
            "title/cause-title block, brief facts, grounds for bail (expand the given "
            "grounds into a persuasive but factual argument), and a prayer clause "
            "requesting bail on such terms as the court deems fit."
        ),
    ),
    "legal_notice_138": Template(
        id="legal_notice_138",
        name="Legal Notice (Section 138 NI Act)",
        category="civil",
        fields=[
            TemplateField("sender_name", "Sender (payee) name"),
            TemplateField("sender_address", "Sender address", type="text"),
            TemplateField("recipient_name", "Recipient (drawer) name"),
            TemplateField("recipient_address", "Recipient address", type="text"),
            TemplateField("cheque_number", "Cheque number"),
            TemplateField("cheque_date", "Cheque date", type="date"),
            TemplateField("cheque_amount_paise", "Cheque amount (paise)", type="number"),
            TemplateField("bank_name", "Drawee bank name"),
            TemplateField("dishonor_date", "Date of dishonor", type="date"),
            TemplateField("dishonor_reason", "Reason for dishonor"),
        ],
        instructions=(
            "Draft a statutory legal notice under Section 138 of the Negotiable "
            "Instruments Act. Must state the cheque particulars, the fact and date of "
            "dishonor, and demand payment of the cheque amount within 15 days of "
            "receipt, failing which legal proceedings will follow."
        ),
    ),
    "rent_agreement": Template(
        id="rent_agreement",
        name="Rent Agreement",
        category="civil",
        fields=[
            TemplateField("landlord_name", "Landlord name"),
            TemplateField("landlord_address", "Landlord address", type="text"),
            TemplateField("tenant_name", "Tenant name"),
            TemplateField("tenant_address", "Tenant address", type="text"),
            TemplateField("property_address", "Property address", type="text"),
            TemplateField("monthly_rent_paise", "Monthly rent (paise)", type="number"),
            TemplateField("security_deposit_paise", "Security deposit (paise)", type="number"),
            TemplateField("start_date", "Tenancy start date", type="date"),
            TemplateField("duration_months", "Duration (months)", type="number"),
        ],
        instructions=(
            "Draft a residential rent agreement covering parties, property "
            "description, rent and deposit terms, duration, maintenance "
            "responsibilities, and termination/renewal conditions."
        ),
    ),
    "vakalatnama": Template(
        id="vakalatnama",
        name="Vakalatnama",
        category="procedural",
        fields=[
            TemplateField("court_name", "Court name"),
            TemplateField("case_number", "Case number"),
            TemplateField("client_name", "Client (executant) name"),
            TemplateField("advocate_name", "Advocate name"),
            TemplateField("bar_council_id", "Bar Council enrollment number"),
        ],
        instructions=(
            "Draft a vakalatnama authorizing the named advocate to appear, plead, and "
            "act on behalf of the client in the specified case before the named court, "
            "including the usual powers to file applications, receive notices, and "
            "compromise with instructions."
        ),
    ),
    "plaint": Template(
        id="plaint",
        name="Plaint (Civil Suit)",
        category="civil",
        fields=[
            TemplateField("court_name", "Court name"),
            TemplateField("plaintiff_name", "Plaintiff name"),
            TemplateField("plaintiff_address", "Plaintiff address", type="text"),
            TemplateField("defendant_name", "Defendant name"),
            TemplateField("defendant_address", "Defendant address", type="text"),
            TemplateField("cause_of_action", "Cause of action", type="text"),
            TemplateField("relief_sought", "Relief sought", type="text"),
            TemplateField(
                "valuation_paise", "Suit valuation (paise)", type="number", required=False
            ),
        ],
        instructions=(
            "Draft a plaint skeleton: cause-title, parties, jurisdiction statement, "
            "facts constituting the cause of action, valuation for court fees, and the "
            "prayer clause with the relief sought."
        ),
    ),
    "written_statement": Template(
        id="written_statement",
        name="Written Statement",
        category="civil",
        fields=[
            TemplateField("court_name", "Court name"),
            TemplateField("case_number", "Case number"),
            TemplateField("defendant_name", "Defendant name"),
            TemplateField("plaintiff_name", "Plaintiff name"),
            TemplateField("response_points", "Response to allegations", type="text"),
            TemplateField(
                "preliminary_objections",
                "Preliminary objections",
                type="text",
                required=False,
            ),
        ],
        instructions=(
            "Draft a written statement responding paragraph-wise in spirit to the "
            "plaint: preliminary objections (if any), a para-wise reply covering the "
            "given response points, and a prayer for dismissal of the suit with costs."
        ),
    ),
    "rti_application": Template(
        id="rti_application",
        name="RTI Application",
        category="administrative",
        fields=[
            TemplateField("applicant_name", "Applicant name"),
            TemplateField("applicant_address", "Applicant address", type="text"),
            TemplateField("public_authority", "Public authority / PIO office"),
            TemplateField("information_sought", "Information sought", type="text"),
        ],
        instructions=(
            "Draft an application under the Right to Information Act, 2005 addressed "
            "to the Public Information Officer, clearly listing the information sought "
            "and requesting it within the statutory 30-day period."
        ),
    ),
    "consumer_complaint": Template(
        id="consumer_complaint",
        name="Consumer Complaint",
        category="civil",
        fields=[
            TemplateField("commission_name", "Consumer commission name"),
            TemplateField("complainant_name", "Complainant name"),
            TemplateField("complainant_address", "Complainant address", type="text"),
            TemplateField("opposite_party_name", "Opposite party name"),
            TemplateField("opposite_party_address", "Opposite party address", type="text"),
            TemplateField(
                "deficiency_details",
                "Deficiency in service / defect details",
                type="text",
            ),
            TemplateField("relief_sought", "Relief sought", type="text"),
        ],
        instructions=(
            "Draft a consumer complaint under the Consumer Protection Act, 2019: "
            "parties, facts describing the deficiency in service or defective goods, "
            "jurisdiction, and the relief/compensation sought."
        ),
    ),
    "affidavit": Template(
        id="affidavit",
        name="Affidavit",
        category="procedural",
        fields=[
            TemplateField("deponent_name", "Deponent name"),
            TemplateField("deponent_address", "Deponent address", type="text"),
            TemplateField("facts_to_affirm", "Facts to affirm", type="text"),
            TemplateField("purpose", "Purpose of affidavit"),
        ],
        instructions=(
            "Draft a general affidavit: deponent's identity, a numbered statement of "
            "the facts to be affirmed on solemn affirmation, and a verification clause."
        ),
    ),
    "reply_to_legal_notice": Template(
        id="reply_to_legal_notice",
        name="Reply to Legal Notice",
        category="civil",
        fields=[
            TemplateField("sender_name", "Sender (replying party) name"),
            TemplateField("original_notice_date", "Date of original notice", type="date"),
            TemplateField("original_notice_summary", "Summary of original notice", type="text"),
            TemplateField("response_points", "Response points", type="text"),
        ],
        instructions=(
            "Draft a reply to a legal notice: acknowledge receipt and date of the "
            "original notice, respond point-by-point to its allegations using the given "
            "response points, and deny any liability not admitted."
        ),
    ),
    "maintenance_petition": Template(
        id="maintenance_petition",
        name="Maintenance Petition",
        category="family",
        fields=[
            TemplateField("court_name", "Court name"),
            TemplateField("petitioner_name", "Petitioner name"),
            TemplateField("respondent_name", "Respondent name"),
            TemplateField("relationship", "Relationship to respondent"),
            TemplateField(
                "petitioner_income_details", "Petitioner's income/needs", type="text"
            ),
            TemplateField(
                "respondent_income_details",
                "Respondent's income (if known)",
                type="text",
                required=False,
            ),
            TemplateField(
                "maintenance_amount_sought_paise",
                "Maintenance amount sought (paise)",
                type="number",
            ),
        ],
        instructions=(
            "Draft a maintenance petition stating the relationship between the "
            "parties, the petitioner's financial needs and the respondent's means (as "
            "known), and the monthly maintenance amount sought."
        ),
    ),
    "anticipatory_bail": Template(
        id="anticipatory_bail",
        name="Anticipatory Bail Application",
        category="criminal",
        fields=[
            TemplateField("court_name", "Court name"),
            TemplateField(
                "case_number", "Case / FIR number (if registered)", required=False
            ),
            TemplateField("applicant_name", "Applicant name"),
            TemplateField("sections_apprehended", "Sections apprehended"),
            TemplateField(
                "apprehension_grounds", "Grounds for apprehension of arrest", type="text"
            ),
        ],
        instructions=(
            "Draft an anticipatory bail application under Section 438 CrPC/482 BNSS: "
            "grounds for the apprehension of arrest, that the applicant is not a flight "
            "risk and will cooperate with investigation, and a prayer for pre-arrest "
            "bail."
        ),
    ),
    "adjournment_application": Template(
        id="adjournment_application",
        name="Adjournment Application",
        category="procedural",
        fields=[
            TemplateField("court_name", "Court name"),
            TemplateField("case_number", "Case number"),
            TemplateField("applicant_name", "Applicant name"),
            TemplateField("reason_for_adjournment", "Reason for adjournment", type="text"),
            TemplateField("next_date_sought", "Next date sought", type="date", required=False),
        ],
        instructions=(
            "Draft a short application seeking adjournment of the hearing, stating the "
            "reason and (if given) the next date sought, undertaking not to seek "
            "further unnecessary adjournments."
        ),
    ),
}


def get_template(template_id: str) -> Template | None:
    return TEMPLATES.get(template_id)


def list_templates() -> list[Template]:
    return list(TEMPLATES.values())
