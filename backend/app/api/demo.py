from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter

from backend.app.config import settings
from backend.app.events.model import EventType
from backend.app.events.publisher import event_publisher
from backend.app.models.enums import (
    IncidentSeverity,
    IncidentSource,
    IncidentStatus,
)
from backend.app.repositories import (
    EvidenceRepository,
    IncidentRepository,
)

router = APIRouter(prefix="/api/demo", tags=["demo"])
stack_trace_content = (
    "Traceback (most recent call last):\n"
    '  File "payment/validator.py", line 42, in validate_payment\n'
    "    raise PaymentValidationException(f'Invalid amount: {amount}')\n"
    "payment.exceptions.PaymentValidationException: Invalid amount: -50.00"
)

log_lines = [
    "2026-08-21T10:01:00Z ERROR [payment-service] "
    "PaymentValidationException: Invalid amount: -50.00",
    "2026-08-21T10:01:01Z ERROR [payment-service] "
    "PaymentValidationException: Invalid amount: -100.00",
    "2026-08-21T10:01:02Z ERROR [payment-service] "
    "PaymentValidationException: Invalid amount: -25.50",
    "2026-08-21T10:01:03Z ERROR [payment-service] "
    "PaymentValidationException: Invalid amount: -200.00",
    "2026-08-21T10:01:04Z ERROR [payment-service] "
    "PaymentValidationException: Invalid amount: -75.00",
    "2026-08-21T10:01:05Z ERROR [payment-service] "
    "PaymentValidationException: Invalid amount: -150.00",
    "2026-08-21T10:01:06Z ERROR [payment-service] "
    "PaymentValidationException: Invalid amount: -30.00",
    "2026-08-21T10:01:07Z ERROR [payment-service] "
    "PaymentValidationException: Invalid amount: -500.00",
    "2026-08-21T10:01:08Z ERROR [payment-service] "
    "PaymentValidationException: Invalid amount: -125.00",
    "2026-08-21T10:01:09Z ERROR [payment-service] "
    "PaymentValidationException: Invalid amount: -45.00",
]
log_content = "\n".join(log_lines)

git_commit_content = (
    "commit a1b2c3d4e5f6\n"
    "Author: deploy-bot <deploy@company.com>\n"
    "Date:   2026-08-21T09:30:00Z\n\n"
    "    Deploy v2.1.0\n\n"
    " M payment/validator.py\n"
    " M payment/config.py\n"
)

git_diff_content = (
    "diff --git a/payment/validator.py b/payment/validator.py\n"
    "index 1234567..abcdefg 100644\n"
    "--- a/payment/validator.py\n"
    "+++ b/payment/validator.py\n"
    "@@ -39,7 +39,7 @@\n"
    " def validate_payment(amount: float) -> bool:\n"
    '     """Validate payment amount."""\n'
    "-    if amount <= 0:\n"
    "+    if amount < 0:\n"
    '         raise PaymentValidationException(f"Invalid amount: {amount}")\n'
    "     return True\n"
)


@router.post("/incidents", status_code=201)
async def create_demo_incident() -> dict:
    now = datetime.now(UTC)
    incident_id = uuid4()
    evidence_ids = [uuid4() for _ in range(4)]

    incident_repo = IncidentRepository(settings.DATABASE_PATH)
    evidence_repo = EvidenceRepository(settings.DATABASE_PATH)

    incident = incident_repo.create_incident(
        id=incident_id,
        source=IncidentSource.MANUAL.value,
        title="Payment service outage - validation regression",
        severity=IncidentSeverity.SEV1.value,
        service="payment-service",
        environment="production",
        status=IncidentStatus.RECEIVED.value,
        description="Negative payment amounts passing validation after boundary check regression",
        stack_traces=[stack_trace_content],
        created_at=now,
        updated_at=now,
        raw_payload={"demo": True},
    )

    evidence_items = [
        {
            "id": evidence_ids[0],
            "source_type": "LOG",
            "source_reference": "payment-service/logs/app.log",
            "content": log_content,
            "metadata": {"log_lines": 10, "error_type": "PaymentValidationException"},
        },
        {
            "id": evidence_ids[1],
            "source_type": "STACK_TRACE",
            "source_reference": "payment-service/stacktraces/latest.txt",
            "content": stack_trace_content,
            "metadata": {
                "exception": "PaymentValidationException",
                "line": 42,
                "file": "validator.py",
            },
        },
        {
            "id": evidence_ids[2],
            "source_type": "GIT_COMMIT",
            "source_reference": "a1b2c3d4e5f6",
            "content": git_commit_content,
            "metadata": {
                "commit_hash": "a1b2c3d4e5f6",
                "version": "v2.1.0",
                "files": ["payment/validator.py", "payment/config.py"],
            },
        },
        {
            "id": evidence_ids[3],
            "source_type": "GIT_DIFF",
            "source_reference": "a1b2c3d4e5f6",
            "content": git_diff_content,
            "metadata": {"commit_hash": "a1b2c3d4e5f6", "files_changed": ["payment/validator.py"]},
        },
    ]

    for item in evidence_items:
        evidence_repo.create_evidence(
            id=item["id"],
            incident_id=incident_id,
            source_type=item["source_type"],
            source_reference=item["source_reference"],
            content=item["content"],
            timestamp=now,
            metadata=item["metadata"],
            created_at=now,
        )

    event_publisher.publish(
        incident_id=incident_id,
        event_type=EventType.INCIDENT_CREATED,
        payload={
            "title": incident["title"],
            "severity": incident["severity"],
            "service": incident["service"],
            "environment": incident["environment"],
        },
    )

    incident_repo.close()
    evidence_repo.close()

    return incident
