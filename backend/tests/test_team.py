"""S01: synthetic identities only, real PostgreSQL locks/RLS, mocked external Auth."""

import asyncio
import base64
import hashlib
import hmac
import json
import time
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from psycopg.errors import InsufficientPrivilege, RaiseException
from test_healthsync import book, payload, query
from test_workspaces import grant

from app.auth import Principal, optional_principal
from app.auth import verified_email as provider_email
from app.config import settings
from app.crypto import decrypt
from app.main import app
from app.staff_delivery import process_one
from app.team import bootstrap


@pytest.fixture
def team_admin(world, login):
    user = login()
    grant(world, user, "admin")
    return user


def branch(world):
    return str(
        query(
            world, "SELECT branch_id FROM healthsync.resources WHERE id=%s", (world["resource"],)
        )[0]["branch_id"]
    )


def invitation(world, recipient, **kwargs):
    return dict(
        email=f"{recipient}@example.com", role="reception", branches=[branch(world)], **kwargs
    )


def raw_token(world, invite_id):
    row = query(
        world, "SELECT * FROM healthsync.staff_deliveries WHERE invitation_id=%s", (invite_id,)
    )[0]
    return decrypt(
        bytes(row["token_ciphertext"]),
        row["key_id"],
        f"staff-delivery:{world['tenant']}:{row['id']}",
    )["token"]


def identity(monkeypatch):
    async def email(principal):
        return f"{principal.subject}@example.com"

    monkeypatch.setattr("app.auth.verified_email", email)


async def create(client, world, recipient):
    result = await client.post(
        world["base"] + "/team/invitations", json=invitation(world, recipient)
    )
    assert result.status_code == 201, result.text
    return result.json()["id"]


async def test_team_tenant_boundaries_privilege_escalation_and_scopes(
    client, world, login, team_admin
):
    assert (await client.get(f"/v1/{world['other']}/team")).status_code == 403
    assert (
        await client.post(f"/v1/{world['other']}/team/invitations", json=invitation(world, uuid4()))
    ).status_code == 403
    fake = invitation(world, uuid4())
    fake["branches"] = [str(uuid4())]
    assert (await client.post(world["base"] + "/team/invitations", json=fake)).status_code == 422
    for role in ("reception", "scheduler", "clinician", "finance", "privacy", None):
        user = login()
        if role:
            grant(world, user, role)
        assert (await client.get(world["base"] + "/team")).status_code == 403
        body = invitation(world, uuid4())
        body["role"] = "admin"
        body["branches"] = []
        assert (
            await client.post(world["base"] + "/team/invitations", json=body)
        ).status_code == 403
    login(team_admin)
    body = invitation(world, uuid4())
    body["active"] = True
    assert (await client.post(world["base"] + "/team/invitations", json=body)).status_code == 422


async def test_valid_invite_verified_recipient_server_grants_repeated_and_concurrent(
    client, world, login, team_admin, monkeypatch
):
    recipient = uuid4()
    invite = await create(client, world, recipient)
    token = raw_token(world, invite)
    assert (
        len(
            query(
                world, "SELECT token_hash FROM healthsync.staff_invitations WHERE id=%s", (invite,)
            )[0]["token_hash"]
        )
        == 32
    )
    listed = await client.get(world["base"] + "/team")
    assert (
        listed.status_code == 200 and token not in listed.text and "token_hash" not in listed.text
    )
    identity(monkeypatch)
    login(uuid4())
    identity(monkeypatch)
    path = world["base"] + "/team/accept"
    assert (await client.post(path, json={"token": token})).status_code == 403
    login(recipient)
    identity(monkeypatch)
    results = await asyncio.gather(*[client.post(path, json={"token": token}) for _ in range(2)])
    assert sorted(r.status_code for r in results) == [200, 409]
    assert (await client.post(path, json={"token": token})).status_code == 409
    membership = query(
        world, "SELECT * FROM healthsync.memberships WHERE auth_user_id=%s", (recipient,)
    )
    assert len(membership) == 1 and membership[0]["role"] == "reception"
    assert (await client.post(path, json={"token": token, "role": "admin"})).status_code == 422
    assert (
        len(
            query(
                world,
                "SELECT * FROM healthsync.membership_branches WHERE auth_user_id=%s",
                (recipient,),
            )
        )
        == 1
    )


@pytest.mark.parametrize("kind", ["expired", "revoked", "replaced"])
async def test_unusable_invites_never_grant(client, world, login, team_admin, monkeypatch, kind):
    recipient = uuid4()
    invite = await create(client, world, recipient)
    token = raw_token(world, invite)
    if kind == "expired":
        query(
            world,
            "UPDATE healthsync.staff_invitations SET created_at=clock_timestamp()-interval '3 days',expires_at=clock_timestamp()-interval '1 day' WHERE id=%s RETURNING id",
            (invite,),
        )
    else:
        response = await client.post(
            world["base"]
            + f"/team/invitations/{invite}/"
            + ("revoke" if kind == "revoked" else "resend"),
            json={"expected_version": 1},
        )
        assert response.status_code == 200
    login(recipient)
    identity(monkeypatch)
    assert (
        await client.post(world["base"] + "/team/accept", json={"token": token})
    ).status_code == 409
    assert not query(
        world, "SELECT 1 FROM healthsync.memberships WHERE auth_user_id=%s", (recipient,)
    )


async def test_member_live_disable_scope_reduction_reactivate_and_optimistic_conflict(
    client, world, login, team_admin
):
    booking = await book(client, world)
    assert booking.status_code == 201
    staff = uuid4()
    grant(world, staff, "reception", branch=True)
    path = world["base"] + f"/team/members/{staff}"
    change = {
        "role": "finance",
        "active": True,
        "expected_version": 1,
        "branches": [branch(world)],
        "resources": [],
    }
    results = await asyncio.gather(*[client.patch(path, json=change) for _ in range(2)])
    assert sorted(r.status_code for r in results) == [200, 409]
    login(staff)  # same subject/token remains; DB role changed
    day = payload(world)["starts_at"][:10]
    assert (
        await client.get(world["base"] + "/staff/appointments", params={"day": day})
    ).status_code == 403
    assert (
        await client.get(world["base"] + "/staff/summary", params={"day": day})
    ).status_code == 200
    login(team_admin)
    change.update(active=False, expected_version=2)
    assert (await client.patch(path, json=change)).status_code == 200
    login(staff)
    assert (
        await client.get(world["base"] + "/staff/summary", params={"day": day})
    ).status_code == 403
    login(team_admin)
    change.update(active=True, expected_version=3)
    assert (await client.patch(path, json=change)).status_code == 200
    login(staff)
    assert (
        await client.get(world["base"] + "/staff/summary", params={"day": day})
    ).status_code == 200
    assert (
        len(
            query(
                world,
                "SELECT id FROM healthsync.appointments WHERE tenant_id=%s",
                (world["tenant"],),
            )
        )
        == 1
    )


async def test_last_admin_concurrent_disable_and_demotion(client, world, login, team_admin):
    other = uuid4()
    grant(world, other, "admin")

    async def alter(user, role, active):
        return await client.patch(
            world["base"] + f"/team/members/{user}",
            json={
                "role": role,
                "active": active,
                "expected_version": 1,
                "branches": [],
                "resources": [],
            },
        )

    # Same active actor can target itself and peer; authorization is reloaded AFTER serialization.
    responses = await asyncio.gather(
        alter(team_admin, "privacy", True), alter(other, "admin", False)
    )
    assert sorted(r.status_code for r in responses) in ([200, 403], [200, 409])
    assert (
        query(
            world,
            "SELECT count(*) AS n FROM healthsync.memberships WHERE tenant_id=%s AND active AND role='admin'",
            (world["tenant"],),
        )[0]["n"]
        == 1
    )
    remaining = query(
        world,
        "SELECT auth_user_id FROM healthsync.memberships WHERE tenant_id=%s AND active AND role='admin'",
        (world["tenant"],),
    )[0]["auth_user_id"]
    login(remaining)
    result = await alter(remaining, "admin", False)
    assert result.status_code == 409


async def test_mfa_missing_auth_provider_failure_closed(
    client, world, login, team_admin, monkeypatch
):

    app.dependency_overrides[optional_principal] = lambda: Principal(
        team_admin, "test-only-token", "aal1"
    )
    assert (await client.get(world["base"] + "/team")).status_code == 403
    app.dependency_overrides[optional_principal] = lambda: Principal(
        team_admin, "test-only-token", "aal2"
    )
    # Restore production identity verifier after login fixture's isolated fake.
    monkeypatch.setattr("app.auth.verified_email", provider_email)
    cfg = settings()
    monkeypatch.setattr(cfg, "supabase_url", "")
    monkeypatch.setattr(cfg, "supabase_publishable_key", "")
    assert (await client.get(world["base"] + "/team")).status_code == 503
    monkeypatch.setattr(cfg, "supabase_url", "https://auth.example.com")
    monkeypatch.setattr(cfg, "supabase_publishable_key", "test")

    async def outage(*args, **kwargs):
        raise httpx.ConnectError("private response must not leak")

    monkeypatch.setattr(httpx.AsyncClient, "get", outage)
    # ASGI client's .get is patched too; use .request.
    response = await client.request("GET", world["base"] + "/team")
    assert response.status_code == 503 and "private response" not in response.text


async def test_bootstrap_requires_operator_owner_no_existing_staff(
    client, world, login, monkeypatch
):
    from app.db import transaction

    user = login()
    identity(monkeypatch)
    principal = Principal(user, "test-only-token", "aal2")
    async with transaction(world["tenant"], None, principal) as (conn, _):
        with pytest.raises(HTTPException):
            await bootstrap(conn, world["tenant"], principal, "first@example.com")
    query(
        world,
        "INSERT INTO platform.operators(auth_user_id,role) VALUES (%s,'owner') RETURNING role",
        (user,),
    )
    async with transaction(world["tenant"], None, principal) as (conn, _):
        result = await bootstrap(conn, world["tenant"], principal, "first@example.com")
        assert result["delivery_state"] == "queued"
    assert not query(
        world, "SELECT * FROM healthsync.memberships WHERE tenant_id=%s", (world["tenant"],)
    )
    grant(world, uuid4(), "admin")
    async with transaction(world["tenant"], None, principal) as (conn, _):
        with pytest.raises(HTTPException):
            await bootstrap(conn, world["tenant"], principal, "second@example.com")


async def test_staff_audit_safe_immutable_and_rls_runtime(client, world, login, team_admin):
    recipient = uuid4()
    invite = await create(client, world, recipient)
    token = raw_token(world, invite)
    events = query(world, "SELECT action,entity,entity_id,changes FROM healthsync.staff_events")
    serialized = json.dumps(events, default=str)
    assert events and token not in serialized and str(recipient) + "@" not in serialized
    assert all(word not in serialized for word in ("ciphertext", "token_hash", "email_hmac"))
    with pytest.raises(RaiseException):
        query(world, "UPDATE healthsync.staff_events SET action='bad' RETURNING id")
    import psycopg

    with psycopg.connect(settings().database_url) as conn:
        conn.execute("SELECT set_config('app.tenant_id',%s,true)", (str(world["other"]),))
        assert not conn.execute("SELECT id FROM healthsync.staff_invitations").fetchall()
        with pytest.raises(InsufficientPrivilege):
            conn.execute("DELETE FROM healthsync.staff_events")


async def test_delivery_disabled_accepted_not_delivered_signed_webhook(
    client, world, login, team_admin, monkeypatch
):
    invite = await create(client, world, uuid4())
    cfg = settings()
    assert not await process_one(world["tenant"])
    monkeypatch.setattr(cfg, "staff_email_send_enabled", True)
    monkeypatch.setattr(cfg, "resend_api_key", "fake")
    monkeypatch.setattr(cfg, "staff_email_from", "demo@example.com")
    monkeypatch.setattr(cfg, "staff_accept_url", "https://clinic.example.com/")
    original = httpx.AsyncClient.post
    calls = []

    async def provider(self, url, **kw):
        if url == "https://api.resend.com/emails":
            calls.append(kw)
            return httpx.Response(200, json={"id": "synthetic-mail"})
        return await original(self, url, **kw)

    monkeypatch.setattr(httpx.AsyncClient, "post", provider)
    assert await process_one(world["tenant"])
    assert not await process_one(world["tenant"])
    assert len(calls) == 1
    row = query(
        world,
        "SELECT state,delivered_at FROM healthsync.staff_deliveries WHERE invitation_id=%s",
        (invite,),
    )[0]
    assert row == {"state": "accepted", "delivered_at": None}
    key = b"fictitious-webhook-key-not-production"
    monkeypatch.setattr(cfg, "resend_webhook_secret", "whsec_" + base64.b64encode(key).decode())
    raw = json.dumps({"type": "email.delivered", "data": {"email_id": "synthetic-mail"}}).encode()
    timestamp = str(int(time.time()))
    signature = base64.b64encode(
        hmac.digest(key, b"evt-1." + timestamp.encode() + b"." + raw, hashlib.sha256)
    ).decode()
    headers = {
        "svix-id": "evt-1",
        "svix-timestamp": timestamp,
        "svix-signature": "v1," + signature,
        "content-type": "application/json",
    }
    path = world["base"] + "/team-delivery-webhook"
    assert (
        await client.post(path, content=raw, headers={**headers, "svix-signature": "v1,bad"})
    ).status_code == 401
    for _ in range(2):
        assert (await client.post(path, content=raw, headers=headers)).status_code == 200
    assert (
        query(
            world, "SELECT state FROM healthsync.staff_deliveries WHERE invitation_id=%s", (invite,)
        )[0]["state"]
        == "delivered"
    )


async def test_branch_and_resource_reduction_applies_to_prior_session(
    client, world, login, team_admin
):
    await book(client, world)
    day = payload(world)["starts_at"][:10]
    staff = uuid4()
    grant(world, staff, "reception", branch=True)
    original_branch = branch(world)
    new_branch = uuid4()
    query(
        world,
        "INSERT INTO healthsync.branches VALUES (%s,%s,'Other Branch','UTC') RETURNING id",
        (world["tenant"], new_branch),
    )
    login(staff)
    response = await client.get(
        world["base"] + "/staff/appointments", params={"day": day, "branch_id": str(new_branch)}
    )
    assert response.status_code == 200 and response.json()["items"] == []
    login(team_admin)
    assert (
        await client.patch(
            world["base"] + f"/team/members/{staff}",
            json={
                "role": "reception",
                "active": True,
                "expected_version": 1,
                "branches": [str(new_branch)],
                "resources": [],
            },
        )
    ).status_code == 200
    login(staff)
    assert (
        await client.get(
            world["base"] + "/staff/appointments", params={"day": day, "branch_id": original_branch}
        )
    ).json()["items"] == []
    doctor = uuid4()
    grant(world, doctor, "clinician", resource=True)
    login(doctor)
    assert (
        len(
            (await client.get(world["base"] + "/staff/appointments", params={"day": day})).json()[
                "items"
            ]
        )
        == 1
    )
    new_resource = uuid4()
    query(
        world,
        "INSERT INTO healthsync.resources SELECT tenant_id,%s,branch_id,specialty_id,'Other Doctor',true FROM healthsync.resources WHERE id=%s RETURNING id",
        (new_resource, world["resource"]),
    )
    login(team_admin)
    assert (
        await client.patch(
            world["base"] + f"/team/members/{doctor}",
            json={
                "role": "clinician",
                "active": True,
                "expected_version": 1,
                "branches": [],
                "resources": [str(new_resource)],
            },
        )
    ).status_code == 200
    login(doctor)
    assert (await client.get(world["base"] + "/staff/appointments", params={"day": day})).json()[
        "items"
    ] == []


async def test_database_guard_rejects_concurrent_last_admin_changes(world, login):
    from psycopg.errors import CheckViolation

    users = [uuid4(), uuid4()]
    for user in users:
        grant(world, user, "admin")

    def disable(user):
        try:
            query(
                world,
                "UPDATE healthsync.memberships SET active=false WHERE tenant_id=%s AND auth_user_id=%s RETURNING active",
                (world["tenant"], user),
            )
            return "changed"
        except CheckViolation:
            return "protected"

    results = await asyncio.gather(*[asyncio.to_thread(disable, u) for u in users])
    assert sorted(results) == ["changed", "protected"]


async def test_staff_member_as_patient_can_manage_own_booking_without_staff_mfa(
    client, world, login
):
    user = login()
    result = await book(client, world)
    grant(world, user, "reception", branch=True)
    app.dependency_overrides[optional_principal] = lambda: Principal(
        user, "test-only-token", "aal1"
    )
    response = await client.patch(
        world["base"] + "/appointments/" + result.json()["id"],
        json={"action": "confirm", "expected_version": 1},
    )
    assert response.status_code == 200
    assert (await client.get(world["base"] + "/team")).status_code == 403


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"id": "wrong", "email": "user@example.com", "email_confirmed_at": "2026-10-23"},
        {"email": "user@example.com"},
        [],
    ],
)
async def test_provider_identity_requires_confirmed_matching_subject(world, monkeypatch, body):
    user = uuid4()
    cfg = settings()
    monkeypatch.setattr(cfg, "supabase_url", "https://identity.example.com")
    monkeypatch.setattr(cfg, "supabase_publishable_key", "synthetic")

    async def response(*args, **kwargs):
        return httpx.Response(200, json=body)

    monkeypatch.setattr(httpx.AsyncClient, "get", response)
    with pytest.raises(HTTPException):
        await provider_email(Principal(user, "synthetic-test-token", "aal2"))


@pytest.mark.parametrize("failure", ["timeout", "429", "500", "invalid_ack"])
async def test_delivery_failure_recovery_does_not_claim_delivery(
    client, world, login, team_admin, monkeypatch, failure
):
    invite = await create(client, world, uuid4())
    cfg = settings()
    for key, value in {
        "staff_email_send_enabled": True,
        "resend_api_key": "fake",
        "staff_email_from": "demo@example.com",
        "staff_accept_url": "https://clinic.example.com/",
    }.items():
        monkeypatch.setattr(cfg, key, value)

    async def fail(*args, **kwargs):
        if failure == "timeout":
            raise httpx.ReadTimeout("secret URL must not leak")
        if failure == "invalid_ack":
            return httpx.Response(200, json={})
        return httpx.Response(int(failure), text="private provider error must not persist")

    monkeypatch.setattr(httpx.AsyncClient, "post", fail)
    query(
        world,
        "UPDATE healthsync.staff_deliveries SET attempts=4 WHERE invitation_id=%s RETURNING id",
        (invite,),
    )
    assert await process_one(world["tenant"])
    row = query(
        world,
        "SELECT state,error_code,delivered_at FROM healthsync.staff_deliveries WHERE invitation_id=%s",
        (invite,),
    )[0]
    assert (
        row["state"] == ("failed" if failure == "429" else "unknown")
        and row["delivered_at"] is None
    )
    assert "private" not in str(row) and "secret" not in str(row)
    assert not await process_one(world["tenant"])


async def test_invitation_directory_search_stays_out_of_url(client, world, login, team_admin):
    recipient = uuid4()
    await create(client, world, recipient)
    found = await client.post(
        world["base"] + "/team/search", json={"email": f"{recipient}@example.com"}
    )
    assert found.status_code == 200 and len(found.json()["items"]) == 1
    assert "@" not in str(found.request.url)
    missing = await client.post(
        world["base"] + "/team/search", json={"email": "nobody@example.com"}
    )
    assert missing.json()["items"] == []


async def test_concurrent_invite_creation_and_scope_edit_require_versions(
    client, world, login, team_admin, monkeypatch
):
    recipient = uuid4()
    body = invitation(world, recipient)
    results = await asyncio.gather(
        *[client.post(world["base"] + "/team/invitations", json=body) for _ in range(2)]
    )
    assert sorted(r.status_code for r in results) == [201, 409]
    invite = next(r for r in results if r.status_code == 201).json()["id"]
    oldtoken = raw_token(world, invite)
    changed = {
        "expected_version": 1,
        "role": "finance",
        "branches": [branch(world)],
        "resources": [],
    }
    updates = await asyncio.gather(
        *[
            client.patch(world["base"] + f"/team/invitations/{invite}", json=changed)
            for _ in range(2)
        ]
    )
    assert sorted(r.status_code for r in updates) == [200, 409]
    replacement = next(r for r in updates if r.status_code == 200).json()["id"]
    login(recipient)
    identity(monkeypatch)
    assert (
        await client.post(world["base"] + "/team/accept", json={"token": oldtoken})
    ).status_code == 409
    response = await client.post(
        world["base"] + "/team/accept", json={"token": raw_token(world, replacement)}
    )
    assert response.status_code == 200 and response.json()["role"] == "finance"


async def test_finance_and_operator_do_not_receive_results_but_own_patient_keeps_flow(
    client, world, login
):
    patient_user = login()
    await book(client, world)
    patient = query(
        world, "SELECT id FROM healthsync.patients WHERE tenant_id=%s", (world["tenant"],)
    )[0]["id"]
    query(
        world,
        "UPDATE healthsync.tenant_modules SET enabled=true WHERE tenant_id=%s AND code='vault' RETURNING code",
        (world["tenant"],),
    )
    result = query(
        world,
        """INSERT INTO healthsync.exam_results
        (tenant_id,patient_id,object_key,uploaded_by,content_sha256,byte_size,scan_status)
        VALUES (%s,%s,'synthetic/private.pdf',%s,%s,32,'clean') RETURNING id""",
        (world["tenant"], patient, patient_user, hashlib.sha256(b"synthetic").digest()),
    )[0]["id"]
    path = world["base"] + f"/exam-results/{result}/access"
    finance = login()
    grant(world, finance, "finance", branch=True)
    assert (await client.post(path)).status_code == 404
    operator = login()
    query(
        world,
        "INSERT INTO platform.operators(auth_user_id,role) VALUES (%s,'owner') RETURNING role",
        (operator,),
    )
    assert (await client.post(path)).status_code == 404
    grant(world, patient_user, "finance", branch=True)
    app.dependency_overrides[optional_principal] = lambda: Principal(
        patient_user, "synthetic-test-token", "aal1"
    )
    response = await client.post(path)
    assert response.status_code == 200 and response.json()["expires_in"] == 900


async def test_new_composite_fks_and_rls_with_runtime_role(client, world, login, team_admin):
    import psycopg
    from psycopg.errors import ForeignKeyViolation

    invite = await create(client, world, uuid4())
    foreign_branch = uuid4()
    query(
        world,
        "INSERT INTO healthsync.branches VALUES (%s,%s,'Other tenant branch','UTC') RETURNING id",
        (world["other"], foreign_branch),
    )
    with psycopg.connect(settings().database_url) as conn:
        for key, value in {
            "app.tenant_id": str(world["tenant"]),
            "app.request_id": str(uuid4()),
            "app.actor_id": str(team_admin),
        }.items():
            conn.execute("SELECT set_config(%s,%s,true)", (key, value))
        with pytest.raises(ForeignKeyViolation):
            conn.execute(
                "INSERT INTO healthsync.invitation_branches VALUES (%s,%s,%s)",
                (world["tenant"], invite, foreign_branch),
            )
    with psycopg.connect(settings().database_url) as conn:
        conn.execute("SELECT set_config('app.tenant_id',%s,true)", (str(world["other"]),))
        for table in [
            "staff_contacts",
            "staff_invitations",
            "invitation_branches",
            "invitation_resources",
            "staff_deliveries",
            "staff_events",
        ]:
            assert conn.execute(f"SELECT count(*) FROM healthsync.{table}").fetchone()[0] == 0
            flags = conn.execute(
                "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass",
                ("healthsync." + table,),
            ).fetchone()
            assert flags == (True, True)


def test_ciphertext_from_cryptography_46_remains_readable_after_security_upgrade(monkeypatch):
    # Public, synthetic interoperability vector generated using 46.0.7.
    # Fixed nonce/key ONLY for this compatibility fixture, never encryption runtime.
    monkeypatch.setattr(settings(), "pii_key_base64", base64.b64encode(bytes([1]) * 32).decode())
    monkeypatch.setattr(settings(), "pii_key_id", "compat-test-v46")
    cipher = bytes.fromhex(
        "0202020202020202020202027cf4ac242b3eaddfe9eecfb132d3aad7d6dcb2af8ec9ec1cadeb85d51b94195d0a92e40d38d4de84b7ab2f7d746a1a04e3"
    )
    assert decrypt(cipher, "compat-test-v46", "compat:synthetic-only") == {
        "email": "synthetic@example.com"
    }
