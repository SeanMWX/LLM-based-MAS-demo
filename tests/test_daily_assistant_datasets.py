from daily_assistant.demo import (
    APP,
    CASE_PROFILES,
    DRIVE_INDEX_BY_ID,
    EMAIL_THREADS_BY_ID,
    POLICY_RULES_BY_ID,
    SANDBOX_ADAPTERS_BY_ID,
    resolve_drive_matches_for_state,
    resolve_email_matches_for_state,
    resolve_policy_matches_for_state,
    search_drive_files,
    search_email_threads,
    search_policy_rules,
)


def test_daily_assistant_case_profiles_reference_existing_datasets():
    for profile in CASE_PROFILES.values():
        for thread_id in profile["email_thread_ids"]:
            assert thread_id in EMAIL_THREADS_BY_ID
        for file_id in profile["drive_file_ids"]:
            assert file_id in DRIVE_INDEX_BY_ID
        for rule_id in profile["policy_rule_ids"]:
            assert rule_id in POLICY_RULES_BY_ID


def test_search_email_threads_returns_expected_deck_match():
    matches = search_email_threads("latest q2 sales deck", top_k=2)

    assert matches
    assert matches[0]["id"] == "email_q2_deck_request"


def test_search_drive_files_returns_expected_receipts_match():
    matches = search_drive_files("march receipts archive", top_k=2)

    assert matches
    assert matches[0]["id"] == "drive_receipts_2026_march_folder"


def test_search_policy_rules_returns_expected_external_confirmation_match():
    matches = search_policy_rules("external share confirmation", top_k=2)

    assert matches
    assert matches[0]["id"] in {
        "policy_external_email_confirmation",
        "policy_external_file_sharing_confirmation",
    }


def test_case_specific_email_and_drive_preferences_are_respected():
    scenario = APP.load_scenarios()["reply_with_latest_quarterly_deck"]
    state = APP.scenario_to_initial_state(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
    )

    email_matches = resolve_email_matches_for_state(state, top_k=3)
    drive_matches = resolve_drive_matches_for_state(state, top_k=3)
    policy_matches = resolve_policy_matches_for_state(state, top_k=3)

    assert [match["id"] for match in email_matches] == ["email_q2_deck_request"]
    assert [match["id"] for match in drive_matches] == ["drive_q2_sales_deck_v5"]
    assert [match["id"] for match in policy_matches] == [
        "policy_draft_only_default",
        "policy_external_email_confirmation",
        "policy_external_file_sharing_confirmation",
    ]


def test_case_profiles_define_phase3a_action_specs():
    deck_profile = CASE_PROFILES["reply_with_latest_quarterly_deck"]
    followup_profile = CASE_PROFILES["morning_followup_triage"]

    assert deck_profile["email_action_specs"]
    assert deck_profile["drive_action_specs"]
    assert followup_profile["email_action_specs"]
    assert followup_profile["drive_action_specs"] == []


def test_sandbox_adapter_dataset_exposes_mail_and_drive_adapters():
    assert "mail_draft_adapter" in SANDBOX_ADAPTERS_BY_ID
    assert "drive_reference_adapter" in SANDBOX_ADAPTERS_BY_ID
    assert SANDBOX_ADAPTERS_BY_ID["mail_draft_adapter"]["domain"] == "email"
    assert SANDBOX_ADAPTERS_BY_ID["drive_reference_adapter"]["domain"] == "drive"
