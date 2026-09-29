"""HTTP layer: authentication, planner forms, results, history and the JSON API."""

from __future__ import annotations

import logging
from functools import wraps

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from services import history as store
from services import shopping
from services.budget import format_inr
from services.gemini_client import build_client
from services.recommender import PLAN_TYPES, allocate_only, generate
from services.validators import (
    ValidationError,
    validate_image,
    validate_jewelry,
    validate_party,
    validate_home,
)
from security import csrf_protect, is_safe_next_url, rate_limited, recommendation_limiter

log = logging.getLogger(__name__)

web = Blueprint("web", __name__)

DEMO_EMAIL = "demo@pocketsmart.ai"
DEMO_PASSWORD = "demo1234"

PLAN_TITLES = {"home": "Home Interior Plan", "party": "Party Plan", "jewelry": "Jewelry Plan"}
PLAN_FORMS = {"home": validate_home, "party": validate_party, "jewelry": validate_jewelry}
PLAN_TAGS = {
    "home": "living-room-modern",
    "party": "party-balloons",
    "jewelry": "jewelry-gold",
}


# --- helpers ---------------------------------------------------------------
def db_path() -> str:
    return str(current_app.config["DATABASE_PATH"])


def current_user() -> dict | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = store.get_user(db_path(), int(user_id))
    if user is None:  # account deleted underneath us
        session.clear()
    return user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None and not current_app.config.get("ALLOW_GUEST"):
            flash("Please sign in to build and save a plan.", "info")
            return redirect(url_for("web.login", next=request.path))
        return view(*args, **kwargs)

    return wrapper


def guest_ok(view):
    """Allow anonymous access when ALLOW_GUEST is on, otherwise require login."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None and not current_app.config.get("ALLOW_GUEST"):
            flash("Please sign in to build and save a plan.", "info")
            return redirect(url_for("web.login", next=request.path))
        return view(*args, **kwargs)

    return wrapper


def _title_for(plan_type: str, payload: dict) -> str:
    if plan_type == "home":
        return f"{payload.get('room_type', 'Room')} makeover - {format_inr(payload.get('budget', 0))}"
    if plan_type == "party":
        return f"{payload.get('event_type', 'Event')} for {payload.get('guest_count', '?')} guests - {format_inr(payload.get('budget', 0))}"
    return f"{payload.get('occasion', 'Occasion')} {str(payload.get('metal', '')).lower()} pick - {format_inr(payload.get('budget', 0))}"


def _persist(plan_type: str, payload: dict, result) -> int | None:
    """Save to history when a user is signed in. Returns the new record id."""
    user = current_user()
    if user is None:
        return None
    record = {
        "request": {k: v for k, v in payload.items() if k != "image_meta"},
        "recommendation": result.to_dict(),
    }
    return store.save_recommendation(
        db_path(),
        user_id=int(user["id"]),
        plan_type=plan_type,
        title=_title_for(plan_type, payload),
        budget=int(payload.get("budget", 0)),
        payload=record,
        source=result.meta.get("source", "ai"),
    )


# --- public pages ----------------------------------------------------------
@web.get("/")
def index():
    return render_template(
        "index.html",
        user=current_user(),
        ai=build_client(current_app.config).status,
        platforms=shopping.platforms_for("home"),
    )


@web.route("/register", methods=["GET", "POST"])
@csrf_protect
@rate_limited()
def register():
    form = {}
    errors: dict[str, str] = {}
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()[:80]
        email = (request.form.get("email") or "").strip().lower()[:160]
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""
        form = {"name": name, "email": email}

        if len(name) < 2:
            errors["name"] = "Please enter your name."
        if "@" not in email or "." not in email.split("@")[-1]:
            errors["email"] = "Enter a valid email address."
        if len(password) < 8:
            errors["password"] = "Use at least 8 characters."
        elif password != confirm:
            errors["confirm"] = "Passwords do not match."

        if not errors:
            if store.email_exists(db_path(), email):
                errors["email"] = "That email is already registered. Sign in instead."
            else:
                user = store.create_user(
                    db_path(), name, email, generate_password_hash(password, method="scrypt")
                )
                if user is None:  # pragma: no cover - race
                    errors["email"] = "That email is already registered."
                else:
                    session.clear()
                    session["user_id"] = int(user["id"])
                    session.permanent = True
                    flash("Welcome to PocketSmart AI. Let's build your plan.", "success")
                    target = request.args.get("next")
                    return redirect(target if is_safe_next_url(target) else url_for("web.dashboard"))

    return render_template("register.html", form=form, errors=errors, user=None), 200


@web.route("/login", methods=["GET", "POST"])
@csrf_protect
@rate_limited()
def login():
    form = {}
    error = None
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()[:160]
        password = request.form.get("password") or ""
        form = {"email": email}
        user = store.get_user_by_email(db_path(), email)
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = int(user["id"])
            session.permanent = True
            flash(f"Signed in as {user['name']}.", "success")
            target = request.args.get("next")
            return redirect(target if is_safe_next_url(target) else url_for("web.dashboard"))
        error = "Incorrect email or password."

    return render_template("login.html", form=form, error=error, user=None), 200


@web.post("/logout")
@csrf_protect
def logout():
    session.clear()
    flash("Signed out.", "info")
    return redirect(url_for("web.index"))


@web.post("/demo-login")
@csrf_protect
@rate_limited()
def demo_login():
    """One-click access with a seeded demo account (created on demand)."""
    user = store.get_user_by_email(db_path(), DEMO_EMAIL)
    if user is None:
        user = store.create_user(
            db_path(), "Demo User", DEMO_EMAIL, generate_password_hash(DEMO_PASSWORD, method="scrypt")
        )
    if user is None:  # pragma: no cover - race
        flash("Could not start the demo. Please register.", "error")
        return redirect(url_for("web.register"))
    session.clear()
    session["user_id"] = int(user["id"])
    session.permanent = True
    flash("Demo mode - your plans are saved under the shared demo account.", "info")
    return redirect(url_for("web.dashboard"))


# --- planners --------------------------------------------------------------
@web.get("/dashboard")
@login_required
def dashboard():
    user = current_user()
    recos = store.list_recommendations(db_path(), user_id=int(user["id"]), limit=6)
    return render_template(
        "dashboard.html",
        user=user,
        recent=recos,
        total=store.count_recommendations(db_path(), int(user["id"])),
        ai=build_client(current_app.config).status,
    )


@web.get("/plan/<plan_type>")
@login_required
def plan_form(plan_type: str):
    if plan_type not in PLAN_TYPES:
        abort(404)
    return render_template(
        f"planner_{plan_type}.html",
        user=current_user(),
        plan_type=plan_type,
        form={},
        errors={},
        platforms=shopping.platforms_for(plan_type),
    )


@web.post("/plan/<plan_type>")
@csrf_protect
@login_required
@rate_limited(recommendation_limiter)
def plan_submit(plan_type: str):
    if plan_type not in PLAN_TYPES:
        abort(404)

    validator = PLAN_FORMS[plan_type]
    image_bytes = None
    image_meta = None
    image_warnings: list[str] = []

    upload = request.files.get("image")
    if plan_type == "jewelry" and upload and upload.filename:
        try:
            validated = validate_image(
                upload,
                max_bytes=current_app.config["MAX_CONTENT_LENGTH"],
                max_dimension=current_app.config["MAX_IMAGE_DIMENSION"],
            )
            image_bytes = validated.data
            image_meta = validated.as_dict()
            image_warnings = validated.warnings
        except ValidationError as exc:
            return (
                render_template(
                    f"planner_{plan_type}.html",
                    user=current_user(),
                    plan_type=plan_type,
                    form=request.form.to_dict(),
                    errors=exc.errors,
                    platforms=shopping.platforms_for(plan_type),
                ),
                400,
            )

    try:
        payload = validator(request.form)
    except ValidationError as exc:
        return (
            render_template(
                f"planner_{plan_type}.html",
                user=current_user(),
                plan_type=plan_type,
                form=request.form.to_dict(),
                errors=exc.errors,
                platforms=shopping.platforms_for(plan_type),
            ),
            400,
        )

    result = generate(
        plan_type,
        payload,
        client=build_client(current_app.config),
        image=image_bytes,
        image_meta=image_meta,
    )
    for message in image_warnings:
        flash(message, "info")

    record_id = _persist(plan_type, payload, result)
    if record_id:
        return redirect(url_for("web.result", rec_id=record_id))
    return render_template(
        "result.html",
        user=current_user(),
        result=result.to_dict(),
        payload=payload,
        record_id=None,
        transient=True,
    )


@web.get("/result/<int:rec_id>")
@login_required
def result(rec_id: int):
    user = current_user()
    record = store.get_recommendation(
        db_path(), rec_id, user_id=int(user["id"]) if user else None
    )
    if record is None:
        flash("That plan was not found.", "error")
        return redirect(url_for("web.dashboard"))
    return render_template(
        "result.html",
        user=user,
        result=record["payload"].get("recommendation", {}),
        payload=record["payload"].get("request", {}),
        record_id=rec_id,
        created_at=record.get("created_at_display"),
        transient=False,
    )


@web.get("/history")
@login_required
def history_page():
    user = current_user()
    plan_filter = request.args.get("type") if request.args.get("type") in PLAN_TYPES else None
    recos = store.list_recommendations(
        db_path(),
        user_id=int(user["id"]),
        limit=50,
        plan_type=plan_filter,
    )
    return render_template(
        "history.html",
        user=user,
        recent=recos,
        plan_filter=plan_filter,
        total=store.count_recommendations(db_path(), int(user["id"])),
    )


@web.post("/history/<int:rec_id>/delete")
@csrf_protect
@login_required
def history_delete(rec_id: int):
    user = current_user()
    if store.delete_recommendation(db_path(), rec_id, user_id=int(user["id"])):
        flash("Plan deleted.", "info")
    else:
        flash("That plan was not found.", "error")
    return redirect(url_for("web.history_page"))


@web.post("/allocate")
@csrf_protect
@login_required
@rate_limited(recommendation_limiter)
def allocate():
    """AI Budget Allocation Engine - form post returning the split."""
    plan_type = request.form.get("plan_type", "home")
    if plan_type not in PLAN_TYPES:
        abort(404)
    try:
        payload = PLAN_FORMS[plan_type](request.form)
    except ValidationError as exc:
        if request.headers.get("X-Requested-With") == "fetch" or request.is_json:
            return jsonify({"ok": False, "errors": exc.errors}), 400
        flash(next(iter(exc.errors.values())), "error")
        return redirect(url_for("web.plan_form", plan_type=plan_type))

    result = allocate_only(plan_type, payload, client=build_client(current_app.config))
    return render_template(
        "allocation.html",
        user=current_user(),
        result=result.to_dict(),
        payload=payload,
        plan_type=plan_type,
    )


# --- JSON API --------------------------------------------------------------
@web.get("/api/health")
def api_health():
    ai = build_client(current_app.config)
    return jsonify(
        {
            "status": "ok",
            "ai": ai.status,
            "plans": list(PLAN_TYPES),
        }
    )


@web.get("/api/platforms")
def api_platforms():
    plan_type = request.args.get("type", "home")
    return jsonify({"plan_type": plan_type, "platforms": shopping.platforms_for(plan_type)})


@web.post("/api/recommend")
@csrf_protect
@login_required
@rate_limited(recommendation_limiter)
def api_recommend():
    if not request.is_json:
        return jsonify({"ok": False, "error": "Send a JSON body."}), 415
    body = request.get_json(silent=True) or {}
    plan_type = str(body.get("plan_type", "home"))
    if plan_type not in PLAN_TYPES:
        return jsonify({"ok": False, "error": f"plan_type must be one of {list(PLAN_TYPES)}"}), 400
    try:
        payload = PLAN_FORMS[plan_type](body)
    except ValidationError as exc:
        return jsonify({"ok": False, "errors": exc.errors}), 400
    except AttributeError:
        return jsonify({"ok": False, "error": "Invalid body."}), 400

    result = generate(plan_type, payload, client=build_client(current_app.config))
    return jsonify({"ok": True, "data": result.to_dict()})

