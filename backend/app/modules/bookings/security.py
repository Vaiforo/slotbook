import hashlib
import re
import secrets

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}\Z")


def new_manage_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def valid_token(token: str | None, stored_hash: str) -> bool:
    return bool(
        token
        and TOKEN_PATTERN.fullmatch(token)
        and secrets.compare_digest(token_hash(token), stored_hash)
    )
