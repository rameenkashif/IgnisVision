"""Idempotent seed: `python -m app.db.seed [--reset-passwords]`.

Creates (only if missing): one station, one demo user per role, default system settings.
Later phases extend this with placeholder training scenarios and a closed demo incident.

Demo password: $SEED_PASSWORD if set, otherwise a random one printed once. Existing users are
left untouched unless --reset-passwords is given.
"""

import argparse
import asyncio
import os
import sys

from sqlalchemy import func, select

from app.core.security import hash_password, password_policy_violation
from app.db.engine import SessionLocal, engine
from app.models import Station, User
from app.services.settings import ensure_defaults
from app.services.users_util import temporary_password

STATION = {"name": "Rescue 1122 — Lahore HQ", "city": "Lahore", "region": "Punjab"}

DEMO_USERS = [
    ("admin", "System Administrator", "admin"),
    ("commander1", "Demo Incident Commander", "incident_commander"),
    ("responder1", "Demo Field Responder", "field_responder"),
    ("trainee1", "Demo Trainee", "trainee"),
    ("trainer1", "Demo Training Staff", "training_staff"),
]


async def seed(reset_passwords: bool = False) -> dict:
    password = os.environ.get("SEED_PASSWORD") or temporary_password()
    if (code := password_policy_violation(password)) is not None:
        raise SystemExit(f"SEED_PASSWORD rejected: {code}")
    pw_hash = hash_password(password)
    created, reset = [], []

    async with SessionLocal() as db:
        station = (
            await db.execute(select(Station).where(Station.name == STATION["name"]))
        ).scalar_one_or_none()
        if station is None:
            station = Station(**STATION)
            db.add(station)
            await db.flush()

        for username, full_name, role in DEMO_USERS:
            user = (
                await db.execute(select(User).where(func.lower(User.username) == username))
            ).scalar_one_or_none()
            if user is None:
                db.add(
                    User(
                        username=username,
                        full_name=full_name,
                        role=role,
                        station_id=station.id,
                        password_hash=pw_hash,
                    )
                )
                created.append(username)
            elif reset_passwords:
                user.password_hash = pw_hash
                user.must_change_password = False
                user.is_active = True
                reset.append(username)

        settings_added = await ensure_defaults(db)
        await db.commit()
    await engine.dispose()
    return {
        "password": password if (created or reset) else None,
        "created": created,
        "reset": reset,
        "settings_added": settings_added,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reset-passwords", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(seed(reset_passwords=args.reset_passwords))

    print(f"Station ready: {STATION['name']}")
    print(f"System settings added: {result['settings_added']}")
    if result["created"] or result["reset"]:
        print("Demo accounts:", ", ".join(result["created"] + result["reset"]))
        print(f"Demo password (all accounts): {result['password']}")
    else:
        print("Demo accounts already exist (use --reset-passwords to set a new password).")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
