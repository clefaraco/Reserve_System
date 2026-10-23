from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from psycopg.errors import RaiseException
from test_healthsync import book, payload, query


def grant(world, user, role, *, branch=False, resource=False):
    query(
        world,
        """INSERT INTO healthsync.memberships (tenant_id,auth_user_id,role,active)
      VALUES (%s,%s,%s,true) ON CONFLICT (tenant_id,auth_user_id) DO UPDATE SET role=EXCLUDED.role RETURNING role""",
        (world["tenant"], user, role),
    )
    if branch:
        branch_id = query(
            world, "SELECT branch_id FROM healthsync.resources WHERE id=%s", (world["resource"],)
        )[0]["branch_id"]
        query(
            world,
            "INSERT INTO healthsync.membership_branches VALUES (%s,%s,%s) ON CONFLICT DO NOTHING RETURNING branch_id",
            (world["tenant"], user, branch_id),
        )
    if resource:
        query(
            world,
            "INSERT INTO healthsync.clinician_resources VALUES (%s,%s,%s) ON CONFLICT DO NOTHING RETURNING resource_id",
            (world["tenant"], user, world["resource"]),
        )


async def test_patient_cannot_self_assign_staff_or_saas_role(client, world, login):
    login()
    profile = (await client.get(world["base"] + "/session")).json()
    assert (
        profile["authenticated"]
        and profile["capabilities"] == []
        and profile["platform_role"] is None
    )
    assert (await client.get(world["base"] + "/organization")).status_code == 403
    assert (await client.get("/v1/platform/tenants")).status_code == 403
    assert (
        await client.get(world["base"] + "/staff/summary", params={"day": "2030-01-01"})
    ).status_code == 403


async def test_reception_requires_explicit_branch_and_does_not_receive_contact(
    client, world, login
):
    await book(client, world)
    user = login()
    grant(world, user, "reception")
    day = payload(world)["starts_at"][:10]
    path = world["base"] + "/staff/appointments"
    assert (await client.get(path, params={"day": day})).json()["items"] == []
    assert (await client.get(world["base"] + "/organization")).json()["branches"] == []
    grant(world, user, "reception", branch=True)
    response = await client.get(path, params={"day": day})
    assert response.status_code == 200 and len(response.json()["items"]) == 1
    row = response.json()["items"][0]
    assert row["patient_name"] == "Paciente Ficticio"
    assert "pii_ciphertext" not in row and "email" not in row and "phone" not in row
    assert (
        await client.get(f"/v1/{world['other']}/staff/appointments", params={"day": day})
    ).status_code == 403
    assert query(
        world,
        "SELECT id FROM healthsync.audit_events WHERE tenant_id=%s AND action='READ_STAFF_CALENDAR'",
        (world["tenant"],),
    )


async def test_doctor_only_sees_assigned_agenda_and_finance_only_aggregates(client, world, login):
    await book(client, world)
    day = payload(world)["starts_at"][:10]
    user = login()
    grant(world, user, "clinician")
    assert (await client.get(world["base"] + "/staff/appointments", params={"day": day})).json()[
        "items"
    ] == []
    grant(world, user, "clinician", resource=True)
    assert (
        len(
            (await client.get(world["base"] + "/staff/appointments", params={"day": day})).json()[
                "items"
            ]
        )
        == 1
    )
    user = login()
    grant(world, user, "finance", branch=True)
    assert (
        await client.get(world["base"] + "/staff/appointments", params={"day": day})
    ).status_code == 403
    summary = await client.get(world["base"] + "/staff/summary", params={"day": day})
    assert summary.json()["counts"] == {"booked": 1}
    assert "patient" not in summary.text
    assert query(
        world,
        "SELECT id FROM healthsync.workspace_events WHERE tenant_id=%s AND action='reports.daily_summary.read'",
        (world["tenant"],),
    )


async def test_attendance_permissions_timing_and_immutable_history(client, world, login):
    result = await book(client, world)
    appointment = result.json()["id"]
    user = login()
    grant(world, user, "clinician", resource=True)
    path = world["base"] + f"/staff/appointments/{appointment}/attendance"
    assert (
        await client.post(path, json={"action": "complete", "expected_version": 1})
    ).status_code == 409
    past = datetime.now(UTC) - timedelta(minutes=30)
    query(
        world,
        """UPDATE healthsync.appointments SET starts_at=%s,ends_at=%s,occupied_until=%s
      WHERE id=%s RETURNING id""",
        (past, past + timedelta(minutes=30), past + timedelta(minutes=45), appointment),
    )
    reception = login()
    grant(world, reception, "reception", branch=True)
    assert (
        await client.post(path, json={"action": "check_in", "expected_version": 1})
    ).status_code == 200
    assert (
        await client.post(path, json={"action": "complete", "expected_version": 1})
    ).status_code == 403
    login(user)
    completed = await client.post(path, json={"action": "complete", "expected_version": 1})
    assert completed.status_code == 200 and completed.json()["status"] == "completed"
    assert (
        await client.post(path, json={"action": "no_show", "expected_version": 1})
    ).status_code == 409
    history = query(
        world,
        "SELECT * FROM healthsync.appointment_events WHERE appointment_id=%s ORDER BY occurred_at",
        (appointment,),
    )
    assert history[0]["status"] == "booked" and history[-1]["status"] == "completed"
    with pytest.raises(RaiseException):
        query(
            world,
            "UPDATE healthsync.appointment_events SET status='tampered' WHERE appointment_id=%s RETURNING id",
            (appointment,),
        )


async def test_tenant_admin_is_not_platform_operator_and_platform_cannot_read_clinical(
    client, world, login
):
    await book(client, world)
    admin = login()
    grant(world, admin, "admin")
    assert (await client.get("/v1/platform/tenants")).status_code == 403
    operator = login()
    query(
        world,
        "INSERT INTO platform.operators (auth_user_id,role) VALUES (%s,'owner') RETURNING role",
        (operator,),
    )
    directory = await client.get("/v1/platform/tenants")
    assert directory.status_code == 200
    assert {str(world["tenant"]), str(world["other"])} <= {
        row["tenant_id"] for row in directory.json()["tenants"]
    }
    assert all(
        set(row) == {"tenant_id", "name", "country", "active"}
        for row in directory.json()["tenants"]
    )
    assert (
        await client.get(
            world["base"] + "/staff/appointments", params={"day": payload(world)["starts_at"][:10]}
        )
    ).status_code == 403
    assert (await client.get(world["base"] + "/appointments")).json() == []


async def test_organization_units_are_tenant_scoped_and_reject_cycles(client, world, login):
    user = login()
    grant(world, user, "admin")
    parent, child = uuid4(), uuid4()
    query(
        world,
        "INSERT INTO healthsync.organization_units (tenant_id,id,kind,name) VALUES (%s,%s,'region','Región') RETURNING id",
        (world["tenant"], parent),
    )
    query(
        world,
        "INSERT INTO healthsync.organization_units (tenant_id,id,parent_id,kind,name) VALUES (%s,%s,%s,'commune','Comuna') RETURNING id",
        (world["tenant"], child, parent),
    )
    data = (await client.get(world["base"] + "/organization")).json()
    assert {str(parent), str(child)} == {u["id"] for u in data["units"]}
    with pytest.raises(RaiseException):
        query(
            world,
            "UPDATE healthsync.organization_units SET parent_id=%s WHERE id=%s RETURNING id",
            (child, parent),
        )


async def test_out_of_branch_scheduler_cannot_modify_an_appointment(client, world, login):
    result = await book(client, world)
    user = login()
    grant(world, user, "scheduler")
    path = world["base"] + "/appointments/" + result.json()["id"]
    assert (
        await client.patch(path, json={"action": "confirm", "expected_version": 1})
    ).status_code == 404
    grant(world, user, "scheduler", branch=True)
    assert (
        await client.patch(path, json={"action": "confirm", "expected_version": 1})
    ).status_code == 200
