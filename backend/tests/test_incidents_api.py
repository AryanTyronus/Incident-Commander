from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient


class TestIncidentsAPI:
    """Tests for POST/GET /api/incidents."""

    def test_create_incident_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/incidents",
            json={
                "source": "MANUAL",
                "title": "Database connection pool exhausted",
                "severity": "SEV1",
                "service": "payment-service",
                "environment": "production",
                "description": "All connections in use",
                "stack_traces": ["at connect (pool.py:42)"],
                "raw_payload": {"custom": True},
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["source"] == "MANUAL"
        assert data["title"] == "Database connection pool exhausted"
        assert data["severity"] == "SEV1"
        assert data["service"] == "payment-service"
        assert data["environment"] == "production"
        assert data["status"] == "RECEIVED"
        assert data["description"] == "All connections in use"
        assert data["stack_traces"] == ["at connect (pool.py:42)"]
        assert data["raw_payload"] == {"custom": True}
        # Verify UUID is valid
        UUID(data["id"])
        # Verify timestamps
        assert data["created_at"] is not None
        assert data["updated_at"] is not None

    def test_create_incident_default_fields(self, client: TestClient) -> None:
        resp = client.post(
            "/api/incidents",
            json={
                "source": "RAW",
                "title": "Something broke",
                "severity": "SEV3",
                "service": "auth-service",
                "environment": "staging",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["description"] == ""
        assert data["stack_traces"] == []
        assert data["raw_payload"] == {}

    def test_create_incident_422_empty_title(self, client: TestClient) -> None:
        resp = client.post(
            "/api/incidents",
            json={
                "source": "MANUAL",
                "title": "",
                "severity": "SEV1",
                "service": "svc",
                "environment": "prod",
            },
        )
        assert resp.status_code == 422

    def test_create_incident_422_blank_title(self, client: TestClient) -> None:
        resp = client.post(
            "/api/incidents",
            json={
                "source": "MANUAL",
                "title": "   ",
                "severity": "SEV1",
                "service": "svc",
                "environment": "prod",
            },
        )
        assert resp.status_code == 422

    def test_create_incident_422_invalid_source(self, client: TestClient) -> None:
        resp = client.post(
            "/api/incidents",
            json={
                "source": "INVALID_SOURCE",
                "title": "Test",
                "severity": "SEV1",
                "service": "svc",
                "environment": "prod",
            },
        )
        assert resp.status_code == 422

    def test_create_incident_422_invalid_severity(self, client: TestClient) -> None:
        resp = client.post(
            "/api/incidents",
            json={
                "source": "MANUAL",
                "title": "Test",
                "severity": "SEV99",
                "service": "svc",
                "environment": "prod",
            },
        )
        assert resp.status_code == 422

    def test_create_incident_422_missing_required(self, client: TestClient) -> None:
        resp = client.post("/api/incidents", json={})
        assert resp.status_code == 422

    def test_get_incident_200(self, client: TestClient) -> None:
        create_resp = client.post(
            "/api/incidents",
            json={
                "source": "MANUAL",
                "title": "Test incident",
                "severity": "SEV2",
                "service": "test-svc",
                "environment": "dev",
            },
        )
        incident_id = create_resp.json()["id"]

        get_resp = client.get(f"/api/incidents/{incident_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == incident_id

    def test_get_incident_404(self, client: TestClient) -> None:
        resp = client.get("/api/incidents/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_get_incident_422_invalid_uuid(self, client: TestClient) -> None:
        resp = client.get("/api/incidents/not-a-uuid")
        assert resp.status_code == 422

    def test_list_incidents_empty(self, client: TestClient) -> None:
        resp = client.get("/api/incidents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["incidents"] == []
        assert data["total"] == 0

    def test_list_incidents_with_data(self, client: TestClient) -> None:
        for i in range(3):
            client.post(
                "/api/incidents",
                json={
                    "source": "MANUAL",
                    "title": f"Incident {i}",
                    "severity": "SEV2",
                    "service": "svc",
                    "environment": "prod",
                },
            )
        resp = client.get("/api/incidents")
        data = resp.json()
        assert len(data["incidents"]) == 3
        assert data["total"] == 3

    def test_list_incidents_pagination(self, client: TestClient) -> None:
        for i in range(5):
            client.post(
                "/api/incidents",
                json={
                    "source": "MANUAL",
                    "title": f"Incident {i}",
                    "severity": "SEV2",
                    "service": "svc",
                    "environment": "prod",
                },
            )
        resp = client.get("/api/incidents?limit=2&offset=0")
        data = resp.json()
        assert len(data["incidents"]) == 2
        assert data["total"] == 5
        assert data["limit"] == 2
        assert data["offset"] == 0

    def test_client_cannot_override_status(self, client: TestClient) -> None:
        resp = client.post(
            "/api/incidents",
            json={
                "source": "MANUAL",
                "title": "Test",
                "severity": "SEV1",
                "service": "svc",
                "environment": "prod",
                "status": "RESOLVED",
            },
        )
        assert resp.status_code == 422

    def test_client_cannot_override_id(self, client: TestClient) -> None:
        resp = client.post(
            "/api/incidents",
            json={
                "id": "11111111-1111-1111-1111-111111111111",
                "source": "MANUAL",
                "title": "Test",
                "severity": "SEV1",
                "service": "svc",
                "environment": "prod",
            },
        )
        # Should either be ignored (201) or rejected (422) - either is acceptable
        assert resp.status_code in (201, 422)

    def test_status_transition_200(self, client: TestClient) -> None:
        create_resp = client.post(
            "/api/incidents",
            json={
                "source": "MANUAL",
                "title": "Transition test",
                "severity": "SEV1",
                "service": "svc",
                "environment": "prod",
            },
        )
        incident_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/incidents/{incident_id}/status",
            json={"status": "TRIAGING"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "TRIAGING"

    def test_status_transition_invalid_409(self, client: TestClient) -> None:
        create_resp = client.post(
            "/api/incidents",
            json={
                "source": "MANUAL",
                "title": "Invalid transition",
                "severity": "SEV1",
                "service": "svc",
                "environment": "prod",
            },
        )
        incident_id = create_resp.json()["id"]

        # RECEIVED -> RESOLVED is not allowed
        resp = client.patch(
            f"/api/incidents/{incident_id}/status",
            json={"status": "RESOLVED"},
        )
        assert resp.status_code == 409

    def test_status_transition_404(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/incidents/00000000-0000-0000-0000-000000000000/status",
            json={"status": "TRIAGING"},
        )
        assert resp.status_code == 404

    def test_raw_payload_preserved(self, client: TestClient) -> None:
        raw = {"key": "value", "nested": {"a": 1}, "list": [1, 2, 3]}
        create_resp = client.post(
            "/api/incidents",
            json={
                "source": "MANUAL",
                "title": "Payload test",
                "severity": "SEV1",
                "service": "svc",
                "environment": "prod",
                "raw_payload": raw,
            },
        )
        incident_id = create_resp.json()["id"]

        get_resp = client.get(f"/api/incidents/{incident_id}")
        assert get_resp.json()["raw_payload"] == raw
