# backend/services/auth_service.py
# Simple file-based token auth — no database needed for MVP
# Production: swap storage with PostgreSQL + bcrypt + JWT

import json
import hashlib
import secrets
import time
from pathlib import Path
from functools import wraps
from flask import request, jsonify

# ------------------------------------------------------------------
# Storage paths (sibling to backend/)
# ------------------------------------------------------------------

_BASE = Path(__file__).resolve().parent.parent
USERS_FILE  = _BASE / "auth_users.json"
TOKENS_FILE = _BASE / "auth_tokens.json"

# ------------------------------------------------------------------
# ROLES
# ------------------------------------------------------------------
ROLES = {"annotator", "reviewer", "admin"}
ROLE_HIERARCHY = {"admin": 3, "reviewer": 2, "annotator": 1}

# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# ------------------------------------------------------------------
# PUBLIC API
# ------------------------------------------------------------------

def register_user(username: str, password: str, role: str = "annotator") -> dict:
    username = username.strip().lower()

    if not username or len(username) < 3:
        return {"ok": False, "message": "Username must be at least 3 characters"}
    if not password or len(password) < 6:
        return {"ok": False, "message": "Password must be at least 6 characters"}
    if role not in ROLES:
        return {"ok": False, "message": f"Invalid role. Choose: {', '.join(ROLES)}"}

    users = _load(USERS_FILE)
    if username in users:
        return {"ok": False, "message": "Username already exists"}

    users[username] = {
        "password_hash": _hash(password),
        "role": role,
        "created_at": int(time.time()),
    }
    _save(USERS_FILE, users)
    return {"ok": True, "username": username, "role": role}


def login_user(username: str, password: str) -> dict:
    username = username.strip().lower()
    users = _load(USERS_FILE)

    user = users.get(username)
    if not user or user["password_hash"] != _hash(password):
        return {"ok": False, "message": "Invalid username or password"}

    # Issue a token valid for 24 hours
    token = secrets.token_hex(32)
    tokens = _load(TOKENS_FILE)
    tokens[token] = {
        "username": username,
        "role": user["role"],
        "expires_at": int(time.time()) + 86400,  # 24 h
    }
    _save(TOKENS_FILE, tokens)

    return {
        "ok": True,
        "token": token,
        "username": username,
        "role": user["role"],
    }


def logout_user(token: str) -> dict:
    tokens = _load(TOKENS_FILE)
    if token in tokens:
        del tokens[token]
        _save(TOKENS_FILE, tokens)
    return {"ok": True}


def verify_token(token: str) -> dict | None:
    """Return user dict if token is valid and not expired, else None."""
    if not token:
        return None
    tokens = _load(TOKENS_FILE)
    entry = tokens.get(token)
    if not entry:
        return None
    if entry["expires_at"] < int(time.time()):
        # Expired — clean up
        del tokens[token]
        _save(TOKENS_FILE, tokens)
        return None
    return {"username": entry["username"], "role": entry["role"]}


def get_token_from_request() -> str | None:
    """Extract Bearer token from Authorization header or X-Auth-Token header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return request.headers.get("X-Auth-Token", "").strip() or None


# ------------------------------------------------------------------
# Flask decorators
# ------------------------------------------------------------------

def require_auth(f):
    """Require any valid token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_from_request()
        user = verify_token(token)
        if not user:
            return jsonify({"status": "error", "message": "Unauthorized — please log in"}), 401
        request.current_user = user
        return f(*args, **kwargs)
    return decorated


def require_role(*roles):
    """Require token AND one of the given roles."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = get_token_from_request()
            user = verify_token(token)
            if not user:
                return jsonify({"status": "error", "message": "Unauthorized — please log in"}), 401
            if user["role"] not in roles:
                return jsonify({
                    "status": "error",
                    "message": f"Forbidden — requires role: {' or '.join(roles)}"
                }), 403
            request.current_user = user
            return f(*args, **kwargs)
        return decorated
    return decorator


def seed_default_users():
    """Create default users if none exist (dev convenience)."""
    users = _load(USERS_FILE)
    if users:
        return  # already seeded

    defaults = [
        ("admin",    "admin123",    "admin"),
        ("reviewer", "reviewer123", "reviewer"),
        ("annotator","annotate123", "annotator"),
    ]
    for username, password, role in defaults:
        register_user(username, password, role)
    print("[AUTH] Default users seeded: admin / reviewer / annotator")