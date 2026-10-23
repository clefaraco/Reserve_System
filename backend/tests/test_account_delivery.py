import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx

from app.config import settings
from app.worker import dispatch_one


async def test_opted_in_account_event_requests_magic_link(client, world, monkeypatch):
    monkeypatch.setattr(settings(), "supabase_url", "https://auth.example.com")
    monkeypatch.setattr(settings(), "supabase_publishable_key", "public-test-key")
    start = (datetime.now(UTC) + timedelta(days=2)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    response = await client.post(
        world["base"] + "/bookings",
        headers={"Idempotency-Key": str(uuid4())},
        json={
            "service_id": str(world["service"]),
            "resource_id": str(world["resource"]),
            "starts_at": start.isoformat(),
            "patient": {"name": "Paciente Ficticio", "email": "patient@example.com"},
            "create_account": True,
            "consent_document_ids": [
                str(d["id"]) for d in world["docs"] if d["kind"] != "whatsapp"
            ],
        },
    )
    assert response.status_code == 201
    calls = []
    factory = httpx.AsyncClient

    async def provider(request):
        calls.append(request)
        assert request.url == "https://auth.example.com/auth/v1/otp"
        assert json.loads(request.content) == {"email": "patient@example.com", "create_user": True}
        assert request.headers["apikey"] == "public-test-key"
        return httpx.Response(200, json={})

    monkeypatch.setattr(
        "app.worker.httpx.AsyncClient",
        lambda **kw: factory(transport=httpx.MockTransport(provider), **kw),
    )
    assert await dispatch_one(world["tenant"])
    assert len(calls) == 1
