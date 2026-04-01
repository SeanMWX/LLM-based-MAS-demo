from pathlib import Path

from coding_agent.demo import APP
from framework.core import coerce_message_text, load_repo_env, parse_env_line


def test_parse_env_line_handles_quotes_and_export_prefix():
    assert parse_env_line('export MINIMAX_MODEL="MiniMax-M2.5"') == (
        "MINIMAX_MODEL",
        "MiniMax-M2.5",
    )
    assert parse_env_line("MINIMAX_MAX_TOKENS='1024'") == (
        "MINIMAX_MAX_TOKENS",
        "1024",
    )
    assert parse_env_line("# comment") is None


def test_load_repo_env_does_not_override_existing_values(tmp_path, monkeypatch):
    import os

    env_path = tmp_path / ".env"
    env_path.write_text(
        "MINIMAX_MODEL=MiniMax-M2.5\nMINIMAX_MAX_TOKENS=1024\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("MINIMAX_MODEL", "AlreadySet")
    monkeypatch.delenv("MINIMAX_MAX_TOKENS", raising=False)

    load_repo_env(Path(env_path))

    assert os.environ["MINIMAX_MODEL"] == "AlreadySet"
    assert os.environ["MINIMAX_MAX_TOKENS"] == "1024"


def test_build_agent_brief_only_includes_prior_roles():
    state = {
        "task": "Do the coding task",
        "repository_context": "Repo context",
        "acceptance_criteria": ["One", "Two"],
        "risk_notes": ["Keep patch minimal"],
        "role_outputs": {
            "planner": '{"plan":["a"]}',
            "coder": '{"patch_summary":["b"]}',
            "tester": '{"verdict":"Pass"}',
            "reviewer": '{"decision":"Approve"}',
        },
    }

    brief = APP.build_agent_brief("tester", state)

    assert "Planner output" in brief
    assert "Coder output" in brief
    assert "Reviewer output" not in brief


def test_coerce_message_text_handles_content_blocks():
    content = [
        {"text": "alpha"},
        {"type": "text", "text": "beta"},
        "gamma",
    ]

    assert coerce_message_text(content) == "alpha\nbeta\ngamma"
