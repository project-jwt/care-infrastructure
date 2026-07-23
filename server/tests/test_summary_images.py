# tests/test_summary_images.py — image attachments on summaries:
#   - primary manages photos (upload/list/raw/delete) on their own summary
#   - the send route attaches them to the email
#   - the recipient contact can view them from the received-summaries side

from core.security import create_access_token
from models.contact_model import TrustedContactLink
from models.summary_model import Summary, SummaryRecipient
from models.user_model import User

# Minimal byte blobs whose leading bytes match each format's magic number —
# that's all the server's _sniff_image_type inspects.
PNG = b"\x89PNG\r\n\x1a\n" + b"fake-png-body"
JPEG = b"\xff\xd8\xff" + b"fake-jpeg-body"
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"fake-webp-body"


async def _user(session, *, email, full_name="U", role="primary"):
    user = User(email=email, password_hash="x", full_name=full_name, role=role)
    session.add(user)
    await session.flush()
    return user


def _auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


async def _summary(session, owner_id):
    summary = Summary(user_id=owner_id, summary_text="hi", transcript="raw")
    session.add(summary)
    await session.flush()
    return summary


def _file(data, filename="photo.png", content_type="image/png"):
    return {"image": (filename, data, content_type)}


# ── upload / list / raw / delete ──────────────────────────────────────────────


async def test_upload_then_list_and_fetch_bytes(client, sessions):
    async with sessions() as s:
        primary = await _user(s, email="p@example.com")
        summary = await _summary(s, primary.id)
        await s.commit()
        sid = summary.id

    up = await client.post(
        f"/api/summaries/{sid}/images", files=_file(PNG), headers=_auth(primary)
    )
    assert up.status_code == 201
    meta = up.json()
    assert meta["contentType"] == "image/png"
    assert meta["byteSize"] == len(PNG)
    assert meta["filename"] == "photo.png"
    image_id = meta["id"]

    lst = await client.get(f"/api/summaries/{sid}/images", headers=_auth(primary))
    assert lst.status_code == 200
    assert [i["id"] for i in lst.json()] == [image_id]

    raw = await client.get(
        f"/api/summaries/{sid}/images/{image_id}/raw", headers=_auth(primary)
    )
    assert raw.status_code == 200
    assert raw.content == PNG
    assert raw.headers["content-type"].startswith("image/png")
    assert raw.headers["x-content-type-options"] == "nosniff"


async def test_delete_removes_the_image(client, sessions):
    async with sessions() as s:
        primary = await _user(s, email="p-del@example.com")
        summary = await _summary(s, primary.id)
        await s.commit()
        sid = summary.id

    up = await client.post(f"/api/summaries/{sid}/images", files=_file(PNG), headers=_auth(primary))
    image_id = up.json()["id"]

    dele = await client.delete(
        f"/api/summaries/{sid}/images/{image_id}", headers=_auth(primary)
    )
    assert dele.status_code == 204

    lst = await client.get(f"/api/summaries/{sid}/images", headers=_auth(primary))
    assert lst.json() == []
    raw = await client.get(f"/api/summaries/{sid}/images/{image_id}/raw", headers=_auth(primary))
    assert raw.status_code == 404


# ── rejections ────────────────────────────────────────────────────────────────


async def test_reject_oversized_image(client, sessions):
    async with sessions() as s:
        primary = await _user(s, email="p-big@example.com")
        summary = await _summary(s, primary.id)
        await s.commit()
        sid = summary.id

    too_big = b"\x89PNG\r\n\x1a\n" + b"x" * (10 * 1024 * 1024 + 1)
    resp = await client.post(f"/api/summaries/{sid}/images", files=_file(too_big), headers=_auth(primary))
    assert resp.status_code == 413


async def test_reject_disallowed_content_type(client, sessions):
    async with sessions() as s:
        primary = await _user(s, email="p-gif@example.com")
        summary = await _summary(s, primary.id)
        await s.commit()
        sid = summary.id

    resp = await client.post(
        f"/api/summaries/{sid}/images",
        files=_file(b"GIF89a...", filename="x.gif", content_type="image/gif"),
        headers=_auth(primary),
    )
    assert resp.status_code == 415


async def test_reject_mislabelled_bytes(client, sessions):
    # Content-type says PNG but the bytes are not an image — magic-byte check
    # must catch it (blocks HTML/SVG smuggled under image/png).
    async with sessions() as s:
        primary = await _user(s, email="p-fake@example.com")
        summary = await _summary(s, primary.id)
        await s.commit()
        sid = summary.id

    resp = await client.post(
        f"/api/summaries/{sid}/images",
        files=_file(b"<html>nope</html>", content_type="image/png"),
        headers=_auth(primary),
    )
    assert resp.status_code == 415


async def test_reject_third_image(client, sessions):
    async with sessions() as s:
        primary = await _user(s, email="p-cap@example.com")
        summary = await _summary(s, primary.id)
        await s.commit()
        sid = summary.id

    for data in (PNG, JPEG):
        ok = await client.post(f"/api/summaries/{sid}/images", files=_file(data, content_type="image/png" if data is PNG else "image/jpeg"), headers=_auth(primary))
        assert ok.status_code == 201
    third = await client.post(f"/api/summaries/{sid}/images", files=_file(WEBP, content_type="image/webp"), headers=_auth(primary))
    assert third.status_code == 409


# ── authorization / scoping ───────────────────────────────────────────────────


async def test_other_primary_cannot_touch_images(client, sessions):
    async with sessions() as s:
        owner = await _user(s, email="owner@example.com")
        intruder = await _user(s, email="intruder@example.com")
        summary = await _summary(s, owner.id)
        await s.commit()
        sid = summary.id

    up = await client.post(f"/api/summaries/{sid}/images", files=_file(PNG), headers=_auth(owner))
    image_id = up.json()["id"]

    # Every verb 404s for a non-owner — same as a nonexistent summary.
    assert (await client.get(f"/api/summaries/{sid}/images", headers=_auth(intruder))).status_code == 404
    assert (await client.post(f"/api/summaries/{sid}/images", files=_file(JPEG, content_type="image/jpeg"), headers=_auth(intruder))).status_code == 404
    assert (await client.get(f"/api/summaries/{sid}/images/{image_id}/raw", headers=_auth(intruder))).status_code == 404
    assert (await client.delete(f"/api/summaries/{sid}/images/{image_id}", headers=_auth(intruder))).status_code == 404


async def test_contact_role_forbidden_on_primary_endpoints(client, sessions):
    async with sessions() as s:
        primary = await _user(s, email="p-role@example.com")
        contact = await _user(s, email="c-role@example.com", role="contact")
        summary = await _summary(s, primary.id)
        await s.commit()
        sid = summary.id

    resp = await client.get(f"/api/summaries/{sid}/images", headers=_auth(contact))
    assert resp.status_code == 403  # require_primary


# ── send attaches the images ──────────────────────────────────────────────────


async def test_send_attaches_images(client, sessions, monkeypatch):
    sent = []

    async def fake_send(to_email, summary_text, from_name=None, attachments=None):
        sent.append({"to": to_email, "attachments": attachments or []})

    monkeypatch.setattr("routers.summaries.send_summary_email", fake_send)

    async with sessions() as s:
        primary = await _user(s, email="p-send@example.com", full_name="Pat")
        contact = await _user(s, email="c-send@example.com", role="contact")
        s.add(TrustedContactLink(owner_id=primary.id, contact_id=contact.id, nickname="Mom"))
        summary = await _summary(s, primary.id)
        await s.commit()
        sid = summary.id

    await client.post(f"/api/summaries/{sid}/images", files=_file(PNG), headers=_auth(primary))

    resp = await client.post(
        f"/api/summaries/{sid}/send",
        json={"contactIds": [contact.id]},
        headers=_auth(primary),
    )
    assert resp.status_code == 200
    assert len(sent) == 1
    atts = sent[0]["attachments"]
    assert len(atts) == 1
    assert atts[0]["content"] == PNG
    assert atts[0]["content_type"] == "image/png"


# ── contact sees images on the received side ──────────────────────────────────


async def test_recipient_sees_and_fetches_images(client, sessions):
    async with sessions() as s:
        primary = await _user(s, email="p-rx@example.com", full_name="Pat")
        contact = await _user(s, email="c-rx@example.com", role="contact")
        summary = await _summary(s, primary.id)
        await s.flush()
        # image on the summary + a delivery record to this contact
        from models.summary_model import SummaryImage

        s.add(SummaryImage(summary_id=summary.id, content_type="image/png", filename="p.png", byte_size=len(PNG), data=PNG))
        s.add(SummaryRecipient(summary_id=summary.id, contact_id=contact.id))
        await s.commit()
        sid = summary.id

    inbox = await client.get("/api/received-summaries", headers=_auth(contact))
    assert inbox.status_code == 200
    item = inbox.json()[0]
    assert len(item["images"]) == 1
    image_id = item["images"][0]["id"]

    raw = await client.get(
        f"/api/received-summaries/{sid}/images/{image_id}/raw", headers=_auth(contact)
    )
    assert raw.status_code == 200
    assert raw.content == PNG
    assert raw.headers["x-content-type-options"] == "nosniff"


async def test_non_recipient_contact_cannot_fetch_image(client, sessions):
    async with sessions() as s:
        primary = await _user(s, email="p-nr@example.com")
        recipient = await _user(s, email="c-nr@example.com", role="contact")
        stranger = await _user(s, email="c-stranger@example.com", role="contact")
        summary = await _summary(s, primary.id)
        await s.flush()
        from models.summary_model import SummaryImage

        img = SummaryImage(summary_id=summary.id, content_type="image/png", filename="p.png", byte_size=len(PNG), data=PNG)
        s.add(img)
        s.add(SummaryRecipient(summary_id=summary.id, contact_id=recipient.id))
        await s.flush()
        await s.commit()
        sid, image_id = summary.id, img.id

    # A contact the summary was NEVER sent to gets 404, not the bytes.
    resp = await client.get(
        f"/api/received-summaries/{sid}/images/{image_id}/raw", headers=_auth(stranger)
    )
    assert resp.status_code == 404
