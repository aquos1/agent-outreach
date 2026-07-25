"""RED tests for discovery filter/cost logic (discovery/logic.py, not yet implemented).

Imports are performed inside each test body so `pytest --collect-only` succeeds
before discovery/logic.py exists (Plan 02-01 implements it).
"""


def test_to_filter_list():
    from discovery.logic import to_filter_list

    assert to_filter_list("Marketing Director, Head of Partnerships") == [
        "Marketing Director",
        "Head of Partnerships",
    ]
    # Empty/whitespace-only input returns an empty list.
    assert to_filter_list("") == []
    assert to_filter_list("   ") == []
    # A single phrase (no comma) becomes a one-element list.
    assert to_filter_list("Marketing Director") == ["Marketing Director"]
    # No AI normalization (D-04) — a straight split-and-strip only.
    assert to_filter_list("software startups, nonprofits") == [
        "software startups",
        "nonprofits",
    ]


def test_has_email_prefilter():
    from discovery.logic import filter_has_email

    candidates = [
        {"id": "1", "has_email": True},
        {"id": "2", "has_email": False},
        {"id": "3"},  # missing has_email key entirely — must be dropped, not crash
    ]
    result = filter_has_email(candidates)
    assert result == [{"id": "1", "has_email": True}]


def test_cost_estimate_no_apollo_call():
    import inspect

    from discovery.logic import CONTACT_CAP, cost_estimate

    assert CONTACT_CAP == 50

    candidates_37 = [{"id": str(i)} for i in range(37)]
    candidates_60 = [{"id": str(i)} for i in range(60)]

    assert cost_estimate(candidates_37) == 37
    assert cost_estimate(candidates_60) == 50

    # No api_key/network argument on the signature — this is a pure local
    # computation with no Apollo call (D-05).
    params = inspect.signature(cost_estimate).parameters
    assert "api_key" not in params
    assert "requests" not in params


def test_path_does_not_affect_filters():
    from discovery.logic import PATH_CONFIG, PATH_OPTIONS, build_search_filters

    company_type = "software startups, nonprofits"
    target_role = "Marketing Director, Head of Partnerships"

    # build_search_filters takes no path argument at all — path selection
    # never changes search filters, only the downstream slug (PATH-02).
    baseline = build_search_filters(company_type, target_role)

    for label in PATH_OPTIONS:
        slug = PATH_CONFIG[label]["slug"]
        assert slug in {"club_sponsorship", "productthon", "client_sourcing"}
        # Regardless of which path a caller "selected" upstream, the filter
        # construction result is identical — path is never passed in.
        result = build_search_filters(company_type, target_role)
        assert result == baseline

    person_titles, org_keyword_tags = baseline
    assert person_titles == ["Marketing Director", "Head of Partnerships"]
    assert org_keyword_tags == ["software startups", "nonprofits"]
