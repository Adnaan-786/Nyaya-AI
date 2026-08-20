from app.ai.templates import TEMPLATES, get_template, list_templates


def test_catalog_has_thirteen_templates():
    # Plan C.9 lists "12 launch templates" but groups "plaint/written
    # statement skeletons" as one bullet; they're kept as two separate
    # templates here since they're genuinely different documents filed
    # by different parties at different stages of a suit. See README's
    # M7 notes for this deviation.
    assert len(TEMPLATES) == 13


def test_every_template_has_at_least_one_required_field():
    for template in list_templates():
        assert any(f.required for f in template.fields), template.id


def test_get_template_returns_none_for_unknown_id():
    assert get_template("not_a_real_template") is None


def test_get_template_returns_template_for_known_id():
    template = get_template("vakalatnama")
    assert template is not None
    assert template.name == "Vakalatnama"


def test_template_field_types_are_from_known_set():
    known_types = {"string", "date", "number", "text"}
    for template in list_templates():
        for f in template.fields:
            assert f.type in known_types, (template.id, f.name, f.type)


def test_all_template_ids_are_unique_and_match_their_key():
    for key, template in TEMPLATES.items():
        assert key == template.id
