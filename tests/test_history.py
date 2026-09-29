"""SQLite persistence tests."""

from __future__ import annotations

from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

from services.history import (
    connect,
    count_recommendations,
    create_user,
    delete_recommendation,
    email_exists,
    get_recommendation,
    get_user,
    get_user_by_email,
    init_db,
    list_recommendations,
    save_recommendation,
)


def test_init_db_is_idempotent(tmp_path):
    db = tmp_path / "nested" / "dir" / "app.db"
    init_db(db)
    init_db(db)
    assert db.exists()
    with connect(db) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"users", "recommendations"} <= tables


def test_create_and_fetch_user(tmp_path):
    db = tmp_path / "a.db"
    init_db(db)
    user = create_user(db, "Aarav", "Aarav@Example.com", generate_password_hash("pw12345678"))
    assert user["email"] == "aarav@example.com"  # normalised
    assert check_password_hash(user["password_hash"], "pw12345678")
    assert get_user_by_email(db, "aarav@example.com")["id"] == user["id"]
    assert get_user(db, user["id"])["name"] == "Aarav"
    assert email_exists(db, "aarav@example.com")


def test_duplicate_email_returns_none(tmp_path):
    db = tmp_path / "b.db"
    init_db(db)
    create_user(db, "Aarav", "a@example.com", "hash")
    assert create_user(db, "Other", "a@example.com", "hash") is None


def test_missing_user_returns_none(tmp_path):
    db = tmp_path / "c.db"
    init_db(db)
    assert get_user_by_email(db, "nobody@example.com") is None
    assert get_user(db, 42) is None


def test_save_and_list_recommendations(tmp_path):
    db = tmp_path / "d.db"
    init_db(db)
    user = create_user(db, "Aarav", "a@example.com", "hash")
    for plan in ("home", "party", "jewelry"):
        save_recommendation(
            db, user_id=user["id"], plan_type=plan, title=f"{plan} plan",
            budget=100000, payload={"a": 1}, source="ai",
        )
    assert count_recommendations(db, user["id"]) == 3
    assert len(list_recommendations(db, user_id=user["id"])) == 3
    assert len(list_recommendations(db, user_id=user["id"], plan_type="party")) == 1
    assert len(list_recommendations(db, user_id=user["id"], limit=2)) == 2


def test_recommendations_are_returned_newest_first(tmp_path):
    db = tmp_path / "e.db"
    init_db(db)
    user = create_user(db, "Aarav", "a@example.com", "hash")
    ids = [
        save_recommendation(db, user_id=user["id"], plan_type="home", title=f"plan {i}",
                            budget=1000, payload={})
        for i in range(3)
    ]
    listed = list_recommendations(db, user_id=user["id"])
    assert [r["id"] for r in listed] == list(reversed(ids))


def test_get_recommendation_parses_json_and_scope(tmp_path):
    db = tmp_path / "f.db"
    init_db(db)
    user = create_user(db, "Aarav", "a@example.com", "hash")
    rec_id = save_recommendation(
        db, user_id=user["id"], plan_type="home", title="t", budget=5000, payload={"x": [1, 2]}
    )
    record = get_recommendation(db, rec_id, user_id=user["id"])
    assert record["payload"] == {"x": [1, 2]}
    assert record["created_at_display"]
    assert get_recommendation(db, rec_id, user_id=999) is None
    assert get_recommendation(db, 9999, user_id=user["id"]) is None


def test_delete_recommendation_respects_ownership(tmp_path):
    db = tmp_path / "g.db"
    init_db(db)
    user = create_user(db, "Aarav", "a@example.com", "hash")
    rec_id = save_recommendation(db, user_id=user["id"], plan_type="home", title="t", budget=1, payload={})
    assert delete_recommendation(db, rec_id, user_id=999) is False
    assert delete_recommendation(db, rec_id, user_id=user["id"]) is True
    assert count_recommendations(db, user["id"]) == 0


def test_deleting_a_user_cascades(tmp_path):
    db = tmp_path / "h.db"
    init_db(db)
    user = create_user(db, "Aarav", "a@example.com", "hash")
    save_recommendation(db, user_id=user["id"], plan_type="home", title="t", budget=1, payload={})
    with connect(db) as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user["id"],))
    assert count_recommendations(db, user["id"]) == 0


def test_corrupt_json_payload_degrades_gracefully(tmp_path):
    db = tmp_path / "i.db"
    init_db(db)
    user = create_user(db, "Aarav", "a@example.com", "hash")
    rec_id = save_recommendation(db, user_id=user["id"], plan_type="home", title="t", budget=1, payload={})
    with connect(db) as conn:
        conn.execute("UPDATE recommendations SET payload = 'not json' WHERE id = ?", (rec_id,))
    assert get_recommendation(db, rec_id)["payload"] == {}


def test_guest_recommendations_have_no_owner(tmp_path):
    db = tmp_path / "j.db"
    init_db(db)
    save_recommendation(db, user_id=None, plan_type="home", title="guest", budget=100, payload={})
    assert count_recommendations(db, None) == 1
    assert count_recommendations(db, 1) == 0
    assert len(list_recommendations(db, user_id=None)) == 1
