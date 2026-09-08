import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

from memanto.cli.migrate.mappers import map_okf
from memanto.cli.migrate.okf_loader import load_okf_bundle

EXAMPLE = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "migrations"
    / "goose-sessions-okf"
    / "goose_sessions_to_okf.py"
)
EXPORT_FIXTURE = EXAMPLE.with_name("export_fixture.py")


def load_example_module():
    spec = importlib.util.spec_from_file_location("goose_sessions_to_okf", EXAMPLE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_export_module():
    load_example_module()
    spec = importlib.util.spec_from_file_location("export_fixture", EXPORT_FIXTURE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_goose_json_export_round_trips_through_okf(tmp_path):
    module = load_example_module()
    source = tmp_path / "goose-export.json"
    source.write_text(
        json.dumps(
            {
                "id": "20260907_1",
                "description": "shipping checklist",
                "working_dir": "/Users/alex/private-project",
                "created_at": "2026-09-07T18:10:00Z",
                "messages": [
                    {
                        "role": "user",
                        "content": "Remember: always run npm test before deploying.",
                    },
                    {
                        "role": "assistant",
                        "content": "Implemented the webhook retry fix and tests pass.",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    summary = module.convert_source(
        source,
        tmp_path / "okf",
        summary_path=tmp_path / "summary.json",
        force=True,
    )

    assert summary["source_sessions"] == 1
    assert summary["source_messages"] == 2
    assert summary["mapped_memories"] == 3
    assert summary["type_counts"] == {"event": 1, "fact": 1, "preference": 1}
    assert (tmp_path / "summary.json").exists()

    rows = map_okf(load_okf_bundle(tmp_path / "okf"))
    assert {row["type"] for row in rows} == {"event", "fact", "preference"}
    content = "\n".join(row["content"] for row in rows)
    assert "npm test before deploying" in content
    assert "/Users/alex" not in content
    assert "[REDACTED_HOME]" in content


def test_goose_sqlite_sessions_are_read_best_effort(tmp_path):
    module = load_example_module()
    db = tmp_path / "sessions.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE sessions (id TEXT PRIMARY KEY, description TEXT, working_dir TEXT, created_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE messages (session_id TEXT, role TEXT, content TEXT, created_at TEXT)"
        )
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?)",
            (
                "20260907_2",
                "release notes",
                r"C:\\Users\\Alex\\AppData\\Roaming\\Block\\goose",
                "2026-09-07T19:00:00Z",
            ),
        )
        conn.execute(
            "INSERT INTO messages VALUES (?, ?, ?, ?)",
            (
                "20260907_2",
                "user",
                "Decision: use structured release notes instead of raw transcripts.",
                "2026-09-07T19:01:00Z",
            ),
        )

    sessions = module.read_goose_sources(db)
    assert len(sessions) == 1
    assert sessions[0].session_id == "20260907_2"
    assert len(sessions[0].messages) == 1

    summary = module.convert_source(db, tmp_path / "okf", force=True)
    assert summary["type_counts"] == {"decision": 1, "event": 1}


def test_current_goose_sqlite_content_json_and_usage_are_preserved(tmp_path):
    module = load_example_module()
    db = tmp_path / "sessions.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE sessions (id TEXT PRIMARY KEY, name TEXT, working_dir TEXT, "
            "created_at TEXT, provider_name TEXT, model_config_json TEXT, "
            "total_tokens INTEGER, input_tokens INTEGER, output_tokens INTEGER)"
        )
        conn.execute(
            "CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, "
            "content_json TEXT, created_timestamp INTEGER)"
        )
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "20260908_3",
                "real local run",
                r"C:\\Users\\Alex\\work",
                "2026-09-08T03:00:00Z",
                "ollama",
                json.dumps({"model_name": "qwen3:4b"}),
                420,
                300,
                120,
            ),
        )
        conn.execute(
            "INSERT INTO messages VALUES (?, ?, ?, ?, ?)",
            (
                1,
                "20260908_3",
                "user",
                json.dumps(
                    [
                        {
                            "type": "text",
                            "text": "Decision: use stable hashes for reconciliation.",
                        }
                    ]
                ),
                1788836400,
            ),
        )
        conn.execute(
            "INSERT INTO messages VALUES (?, ?, ?, ?, ?)",
            (
                2,
                "20260908_3",
                "user",
                json.dumps(
                    [
                        {
                            "type": "text",
                            "text": "<turn-context>private runtime path</turn-context>",
                        }
                    ]
                ),
                1788836401,
            ),
        )

    sessions = module.read_sessions_db(db)
    assert len(sessions) == 1
    assert sessions[0].model == "qwen3:4b"
    assert sessions[0].provider == "ollama"
    assert sessions[0].total_tokens == 420
    assert [message.content for message in sessions[0].messages] == [
        "Decision: use stable hashes for reconciliation."
    ]

    summary = module.convert_source(db, tmp_path / "okf", force=True)
    assert summary["source_tokens"] == 420
    assert summary["source_input_tokens"] == 300
    assert summary["source_output_tokens"] == 120

    selected = module.convert_source(
        db,
        tmp_path / "selected",
        force=True,
        session_ids={"20260908_3"},
    )
    assert selected["source_sessions"] == 1
    assert "Alex" not in selected["output_path"]


def test_fixture_export_selects_only_the_requested_session(tmp_path):
    module = load_export_module()
    db = tmp_path / "sessions.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE sessions (id TEXT PRIMARY KEY, description TEXT, created_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE messages (session_id TEXT, role TEXT, content TEXT, created_at TEXT)"
        )
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?)",
            ("unnamed", None, "2026-09-08T01:00:00Z"),
        )
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?)",
            ("wanted", "selected run", "2026-09-08T02:00:00Z"),
        )
        conn.execute(
            "INSERT INTO messages VALUES (?, ?, ?, ?)",
            ("wanted", "user", "Remember this session.", "2026-09-08T02:01:00Z"),
        )

    exported = module.export_session(
        db,
        session_id="wanted",
        session_name=None,
        goose_version="test",
    )

    assert exported["id"] == "wanted"
    assert exported["description"] == "selected run"
