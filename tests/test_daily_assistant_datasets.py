from daily_assistant.demo import (
    APP,
    CASE_PROFILES,
    DRIVE_INDEX_BY_ID,
    EMAIL_THREADS_BY_ID,
    resolve_drive_matches_for_state,
    resolve_email_matches_for_state,
    search_drive_files,
    search_email_threads,
)


def test_daily_assistant_case_profiles_reference_existing_datasets():
    for profile in CASE_PROFILES.values():
        for thread_id in profile["email_thread_ids"]:
            assert thread_id in EMAIL_THREADS_BY_ID
        for file_id in profile["drive_file_ids"]:
            assert file_id in DRIVE_INDEX_BY_ID


def test_search_email_threads_returns_expected_deck_match():
    matches = search_email_threads("latest q2 sales deck", top_k=2)

    assert matches
    assert matches[0]["id"] == "email_q2_deck_request"


def test_search_drive_files_returns_expected_receipts_match():
    matches = search_drive_files("march receipts archive", top_k=2)

    assert matches
    assert matches[0]["id"] == "drive_receipts_2026_march_folder"


def test_case_specific_email_and_drive_preferences_are_respected():
    scenario = APP.load_scenarios()["reply_with_latest_quarterly_deck"]
    state = APP.scenario_to_initial_state(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
    )

    email_matches = resolve_email_matches_for_state(state, top_k=3)
    drive_matches = resolve_drive_matches_for_state(state, top_k=3)

    assert [match["id"] for match in email_matches] == ["email_q2_deck_request"]
    assert [match["id"] for match in drive_matches] == ["drive_q2_sales_deck_v5"]
