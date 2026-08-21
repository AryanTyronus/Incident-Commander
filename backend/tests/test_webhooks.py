from __future__ import annotations

from fastapi.testclient import TestClient

from backend.tests.conftest import make_pagerduty_payload, make_sentry_payload


class TestPagerDutyWebhook:
    """Tests for POST /api/webhooks/pagerduty."""

    def test_valid_payload_200(self, client: TestClient) -> None:
        payload = make_pagerduty_payload()
        resp = client.post("/api/webhooks/pagerduty", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "incident_id" in data
        assert data["status"] == "RECEIVED"
        assert "created" in data["message"].lower()

    def test_correct_normalization(self, client: TestClient) -> None:
        payload = make_pagerduty_payload(
            title="High latency on /api/users",
            urgency="low",
            service_name="user-service",
        )
        resp = client.post("/api/webhooks/pagerduty", json=payload)
        assert resp.status_code == 200

        incident_id = resp.json()["incident_id"]
        get_resp = client.get(f"/api/incidents/{incident_id}")
        data = get_resp.json()
        assert data["source"] == "PAGERDUTY"
        assert data["title"] == "High latency on /api/users"
        assert data["severity"] == "SEV3"  # low -> SEV3
        assert data["service"] == "user-service"

    def test_raw_payload_preserved(self, client: TestClient) -> None:
        payload = make_pagerduty_payload()
        resp = client.post("/api/webhooks/pagerduty", json=payload)
        incident_id = resp.json()["incident_id"]

        get_resp = client.get(f"/api/incidents/{incident_id}")
        assert get_resp.json()["raw_payload"] == payload

    def test_duplicate_delivery(self, client: TestClient) -> None:
        payload = make_pagerduty_payload(event_id="pd-dup-001")
        resp1 = client.post("/api/webhooks/pagerduty", json=payload)
        resp2 = client.post("/api/webhooks/pagerduty", json=payload)

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["incident_id"] == resp2.json()["incident_id"]

    def test_empty_payload_400(self, client: TestClient) -> None:
        resp = client.post("/api/webhooks/pagerduty", json={})
        assert resp.status_code == 400

    def test_multiple_incidents_distinct(self, client: TestClient) -> None:
        p1 = make_pagerduty_payload(event_id="pd-1")
        p2 = make_pagerduty_payload(event_id="pd-2")
        r1 = client.post("/api/webhooks/pagerduty", json=p1)
        r2 = client.post("/api/webhooks/pagerduty", json=p2)
        assert r1.json()["incident_id"] != r2.json()["incident_id"]


class TestSentryWebhook:
    """Tests for POST /api/webhooks/sentry."""

    def test_valid_payload_200(self, client: TestClient) -> None:
        payload = make_sentry_payload()
        resp = client.post("/api/webhooks/sentry", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "incident_id" in data
        assert data["status"] == "RECEIVED"
        assert "created" in data["message"].lower()

    def test_correct_normalization(self, client: TestClient) -> None:
        payload = make_sentry_payload(
            message="ConnectionRefused: Redis unavailable",
            level="fatal",
            project_name="cache-service",
        )
        resp = client.post("/api/webhooks/sentry", json=payload)
        assert resp.status_code == 200

        incident_id = resp.json()["incident_id"]
        get_resp = client.get(f"/api/incidents/{incident_id}")
        data = get_resp.json()
        assert data["source"] == "SENTRY"
        assert data["severity"] == "SEV1"  # fatal -> SEV1
        assert data["service"] == "cache-service"

    def test_raw_payload_preserved(self, client: TestClient) -> None:
        payload = make_sentry_payload()
        resp = client.post("/api/webhooks/sentry", json=payload)
        incident_id = resp.json()["incident_id"]

        get_resp = client.get(f"/api/incidents/{incident_id}")
        assert get_resp.json()["raw_payload"] == payload

    def test_duplicate_delivery(self, client: TestClient) -> None:
        payload = make_sentry_payload(event_id="sentry-dup-001")
        resp1 = client.post("/api/webhooks/sentry", json=payload)
        resp2 = client.post("/api/webhooks/sentry", json=payload)

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["incident_id"] == resp2.json()["incident_id"]

    def test_empty_payload_400(self, client: TestClient) -> None:
        resp = client.post("/api/webhooks/sentry", json={})
        assert resp.status_code == 400

    def test_multiple_incidents_distinct(self, client: TestClient) -> None:
        p1 = make_sentry_payload(event_id="sentry-1")
        p2 = make_sentry_payload(event_id="sentry-2")
        r1 = client.post("/api/webhooks/sentry", json=p1)
        r2 = client.post("/api/webhooks/sentry", json=p2)
        assert r1.json()["incident_id"] != r2.json()["incident_id"]

    def test_stack_traces_extracted(self, client: TestClient) -> None:
        payload = make_sentry_payload()
        resp = client.post("/api/webhooks/sentry", json=payload)
        incident_id = resp.json()["incident_id"]

        get_resp = client.get(f"/api/incidents/{incident_id}")
        data = get_resp.json()
        assert len(data["stack_traces"]) > 0
        assert "render" in data["stack_traces"][0]
        assert "fetchUserData" in data["stack_traces"][0]
