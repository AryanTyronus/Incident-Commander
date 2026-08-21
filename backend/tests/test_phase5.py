from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from backend.app.main import app


async def test_health() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_ready() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "checks" in data
    assert "sqlite" in data["checks"]


async def test_create_demo_incident() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/demo/incidents")
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Payment service outage - validation regression"
    assert data["severity"] == "SEV1"
    assert data["service"] == "payment-service"


async def test_get_events() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create demo incident first
        demo = (await client.post("/api/demo/incidents")).json()
        incident_id = demo["id"]
        # Get events
        resp = await client.get(f"/api/incidents/{incident_id}/events")
    assert resp.status_code == 200
    data = resp.json()
    assert data["incident_id"] == incident_id
    assert isinstance(data["events"], list)
    assert data["total"] >= 0


async def test_get_evidence() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        demo = (await client.post("/api/demo/incidents")).json()
        incident_id = demo["id"]
        resp = await client.get(f"/api/incidents/{incident_id}/evidence")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 4  # Demo creates 4 evidence items
