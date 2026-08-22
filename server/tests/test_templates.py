"""The draftsman catalogue. These are contract assertions: the app builds its forms
from `fields`, so a wrong `type` renders the wrong keyboard and, on a money field,
a hundred-fold error."""

from app.ai.templates import TEMPLATES, get_template, list_templates

KNOWN_FIELD_TYPES = {"string", "date", "number", "text"}


def test_the_launch_catalogue_is_complete() -> None:
    # C.9 says "12 launch templates" but groups plaint and written statement as one
    # bullet. They are kept separate here because they are genuinely different
    # documents, filed by different parties at different stages of the same suit.
    assert len(TEMPLATES) == 13


def test_every_template_has_at_least_one_required_field() -> None:
    for template in list_templates():
        assert any(f.required for f in template.fields), template.id


def test_unknown_ids_return_none_rather_than_raising() -> None:
    assert get_template("not_a_real_template") is None


def test_a_known_id_returns_its_template() -> None:
    template = get_template("vakalatnama")

    assert template is not None
    assert template.name == "Vakalatnama"


def test_field_types_are_all_ones_the_app_can_render() -> None:
    for template in list_templates():
        for field in template.fields:
            assert field.type in KNOWN_FIELD_TYPES, (template.id, field.name, field.type)


def test_money_fields_are_named_in_paise() -> None:
    """B.1.5: every amount in this server is integer paise. A money field whose name
    does not say so is one a client will eventually fill in rupees."""
    for template in list_templates():
        for field in template.fields:
            if field.type == "number" and (
                "amount" in field.name or "rent" in field.name or "deposit" in field.name
            ):
                assert field.name.endswith("_paise"), (template.id, field.name)


def test_every_key_matches_the_id_of_the_template_it_holds() -> None:
    for key, template in TEMPLATES.items():
        assert key == template.id
