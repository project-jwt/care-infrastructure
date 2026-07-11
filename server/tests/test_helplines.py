# tests/test_helplines.py — the pre-loaded helplines (F7).
#
# Covers the two pieces this feature adds:
#   - db/seed.ensure_seeded (the mechanism main.py's lifespan runs — tests
#     drive it directly because ASGITransport never runs lifespan)
#   - GET /api/helplines (router shape + the login-only gate: both roles OK)

from core.security import create_access_token
from db import seed
from models import helpline_model
from models.helpline_model import Helpline
from models.user_model import User


async def _user(session, *, email, full_name, role):
    # password_hash is NOT NULL but never checked here (we mint tokens directly),
    # so a placeholder string beats paying for a real bcrypt hash.
    user = User(email=email, password_hash="x", full_name=full_name, role=role)
    session.add(user)
    await session.flush()  # assign the id without ending the transaction
    return user


def _auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


# ── Seed mechanism ───────────────────────────────────────────────────────────


async def test_ensure_seeded_inserts_once(session):
    # First call on an empty table seeds the spec's AARP row...
    await seed.ensure_seeded(session)
    rows = await helpline_model.list_all(session)
    assert len(rows) == len(seed.HELPLINES) == 1
    assert rows[0].phone == "877-908-3360"

    # ...and a second call (every later server restart) adds nothing.
    await seed.ensure_seeded(session)
    assert len(await helpline_model.list_all(session)) == 1


# ── HTTP endpoint ────────────────────────────────────────────────────────────


async def test_list_helplines_shape_and_both_roles(client, sessions):
    async with sessions() as s:
        primary = await _user(s, email="p@example.com", full_name="Prim", role="primary")
        contact = await _user(s, email="c@example.com", full_name="Con", role="contact")
        s.add(
            Helpline(
                name="AARP Fraud Watch Network Helpline",
                phone="877-908-3360",
                hours="Monday to Friday, 8am to 8pm ET",
                description="Free scam help.",
            )
        )
        await s.commit()
        primary_tok, contact_tok = _auth(primary), _auth(contact)

    # No role gate (spec): a primary AND a contact both get the list.
    for headers in (primary_tok, contact_tok):
        resp = await client.get("/api/helplines", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        # Exact contract shape — nothing extra leaks, nothing is missing.
        assert set(data[0].keys()) == {"id", "name", "phone", "hours", "description"}
        assert data[0]["phone"] == "877-908-3360"


async def test_list_helplines_rejects_anonymous(client):
    resp = await client.get("/api/helplines")
    assert resp.status_code == 401
    assert "message" in resp.json()
