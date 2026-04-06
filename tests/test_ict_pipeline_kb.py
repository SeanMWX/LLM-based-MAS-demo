from ict_pipeline.demo import (
    APP,
    KB_ARTICLES,
    KB_ARTICLES_BY_ID,
    read_kb_article,
    resolve_kb_matches_for_state,
    search_kb_articles,
)


def test_kb_article_fixture_has_expected_shape():
    assert len(KB_ARTICLES) >= 4

    for article in KB_ARTICLES:
        assert sorted(article) == sorted(
            [
                "category",
                "escalation_queue",
                "id",
                "keywords",
                "recommended_actions",
                "requires_approval",
                "requires_human",
                "summary",
                "title",
            ]
        )
        assert article["id"] in KB_ARTICLES_BY_ID
        assert isinstance(article["keywords"], list)
        assert isinstance(article["recommended_actions"], list)


def test_search_kb_articles_returns_expected_vpn_article_first():
    results = search_kb_articles(
        "Employee reports a locked VPN account after failed logins and needs remote access restored before a customer call.",
        top_k=2,
    )

    assert results[0]["id"] == "kb_vpn_locked_account_reset"
    assert results[0]["score"] >= results[-1]["score"]


def test_read_kb_article_returns_full_article():
    article = read_kb_article("kb_finance_drive_access_requires_approval")

    assert article["category"] == "onboarding"
    assert article["requires_approval"] is True
    assert "request explicit approval for the finance drive" in article[
        "recommended_actions"
    ]


def test_resolve_kb_matches_for_state_uses_phase2_ordering():
    scenario = APP.load_scenarios()["new_hire_access_bundle"]
    state = APP.scenario_to_initial_state(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
    )

    matches = resolve_kb_matches_for_state(state, top_k=3)

    assert [match["id"] for match in matches[:2]] == [
        "kb_new_hire_standard_access_bundle",
        "kb_finance_drive_access_requires_approval",
    ]
