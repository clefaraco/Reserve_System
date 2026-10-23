"""Local-only functional check. Creates synthetic bookings in the demo tenant."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx

base = "http://127.0.0.1:8000"
tenant = "10000000-0000-4000-8000-000000000001"
with httpx.Client(base_url=base, timeout=15) as client:
    assert client.get("/health").json() == {"status": "ok"}
    catalog = client.get(f"/v1/{tenant}/catalog").json()
    assert "Demo" in catalog["tenant"]
    assert all(d["version"].startswith("demo") for d in catalog["documents"])
    service = catalog["services"][0]
    day = (datetime.now(UTC) + timedelta(days=3)).date().isoformat()
    available = client.get(
        f"/v1/{tenant}/availability",
        params={
            "day": day,
            "service_id": service["service_id"],
            "resource_id": service["resource_id"],
        },
    )
    available.raise_for_status()
    slot = available.json()["slots"][0]
    payload = {
        "service_id": service["service_id"],
        "resource_id": service["resource_id"],
        "starts_at": slot,
        "patient": {"name": "Paciente de prueba", "email": "synthetic@example.com"},
        "consent_document_ids": [d["id"] for d in catalog["documents"] if d["kind"] != "whatsapp"],
    }
    key = str(uuid4())
    first = client.post(f"/v1/{tenant}/bookings", json=payload, headers={"Idempotency-Key": key})
    assert first.status_code == 201, first.status_code
    retry = client.post(f"/v1/{tenant}/bookings", json=payload, headers={"Idempotency-Key": key})
    assert retry.status_code == 201 and retry.json()["id"] == first.json()["id"]
    conflict = client.post(
        f"/v1/{tenant}/bookings", json=payload, headers={"Idempotency-Key": str(uuid4())}
    )
    assert conflict.status_code == 409
with httpx.Client(base_url="http://127.0.0.1:5173", timeout=10) as client:
    assert "HealthSync" in client.get("/").text
    assert client.get("/health").json() == {"status": "ok"}
print(
    "PASS: API readiness, catalog, availability, booking, idempotent retry, conflict, frontend and proxy."
)
