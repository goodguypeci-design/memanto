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


def load_example_module():
    spec = importlib.util.spec_from_file_location("goose_sessions_to_okf", EXAMPLE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
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
