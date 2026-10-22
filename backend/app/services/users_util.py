import secrets
import string

from app.core.security import password_policy_violation


def temporary_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if password_policy_violation(pw) is None:
            return pw
