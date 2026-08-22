"""Tests that aggregated investigation findings keep their declared type.

``InvestigationState.findings`` is typed ``list[AgentResult]``, but the commander
filled it with the raw ``AgentRun.output`` dicts the executor stores
(``AgentResult.model_dump()``). Assigning to a model field does not validate, so
the mismatch only surfaced when ``_persist_state`` serialized the state, once per
agent, per persist:

    PydanticSerializationUnexpectedValue: Expected `AgentResult` -
    serialized value may not be as expected
    [field_name='findings', input_value={'agent_name': 'log_triage', ...}, input_type=dict]

The commander now rebuilds the models, so the field holds what it declares.
"""

from __future__ import annotations

import warnings
from uuid import UUID, uuid4

from backend.app.agents.commander import IncidentCommander
from backend.app.agents.registry import AgentRegistry
from backend.app.llm.fake import FakeLLMProvider
from backend.app.models.agent_schemas import (
    AgentResult,
    InvestigationStage,
    InvestigationState,
)
from backend.app.orchestration.execution import AgentExecutor
from backend.tests.test_commander import (
    FakeAgentRunRepository,
    FakeIncidentRepository,
    FakeInvestigationRepository,
    MockAgent,
    MockFailingAgent,
    make_plan_json,
)

AGENT_NAMES = ("log_triage", "git_forensics", "runbook")


def _serialization_warnings(records: list[warnings.WarningMessage]) -> list[str]:
    """Pydantic serializer complaints among the captured warnings."""
    return [
        str(r.message)
        for r in records
        if "PydanticSerializationUnexpectedValue" in str(r.message)
        or "Expected `AgentResult`" in str(r.message)
    ]


class TestAggregatedFindingsAreAgentResults:
    def setup_method(self) -> None:
        self.run_repo = FakeAgentRunRepository()
        self.incident_repo = FakeIncidentRepository()
        self.investigation_repo = FakeInvestigationRepository()
        self.executor = AgentExecutor(self.run_repo)
        self.registry = AgentRegistry()

    def _commander(self, llm: FakeLLMProvider) -> IncidentCommander:
        return IncidentCommander(
            llm=llm,
            repo=self.incident_repo,
            agent_run_repo=self.run_repo,
            investigation_repo=self.investigation_repo,
            executor=self.executor,
            registry=self.registry,
        )

    def _incident(self) -> UUID:
        incident_id = uuid4()
        self.incident_repo.add_incident({
            "id": incident_id,
            "title": "Payment service outage",
            "severity": "SEV1",
            "service": "payment-service",
            "environment": "production",
            "status": "RECEIVED",
            "description": "Negative amounts passing validation",
        })
        return incident_id

    def _plan_for(self, *agent_names: str) -> str:
        return make_plan_json([
            {
                "agent_name": name,
                "purpose": f"Run {name}",
                "priority": i + 1,
                "input": {},
            }
            for i, name in enumerate(agent_names)
        ])

    async def _investigate(self, *agent_names: str) -> InvestigationState:
        incident_id = self._incident()
        for name in agent_names:
            self.registry.register(MockAgent(name))
        llm = FakeLLMProvider(responses=[self._plan_for(*agent_names)])
        return await self._commander(llm).investigate(incident_id)

    async def test_findings_hold_agent_results_not_dicts(self) -> None:
        state = await self._investigate(*AGENT_NAMES)

        assert state.status == InvestigationStage.COMPLETED
        assert len(state.findings) == len(AGENT_NAMES)
        assert all(isinstance(f, AgentResult) for f in state.findings), (
            f"got {[type(f).__name__ for f in state.findings]}"
        )

    async def test_investigation_emits_no_serializer_warnings(self) -> None:
        """The reported symptom: one warning per agent, on every persist."""
        with warnings.catch_warnings(record=True) as records:
            warnings.simplefilter("always")
            await self._investigate(*AGENT_NAMES)

        assert _serialization_warnings(records) == []

    async def test_persisting_the_state_emits_no_serializer_warnings(self) -> None:
        state = await self._investigate(*AGENT_NAMES)

        with warnings.catch_warnings(record=True) as records:
            warnings.simplefilter("always")
            state.model_dump_json()
            state.model_dump(mode="json")

        assert _serialization_warnings(records) == []

    async def test_findings_carry_each_agent_result(self) -> None:
        state = await self._investigate(*AGENT_NAMES)

        by_name = {f.agent_name: f for f in state.findings}
        assert set(by_name) == set(AGENT_NAMES)
        for name in AGENT_NAMES:
            assert by_name[name].summary == f"{name} done"
            assert by_name[name].confidence == 0.5

    async def test_failed_agents_contribute_no_findings(self) -> None:
        incident_id = self._incident()
        self.registry.register(MockAgent("log_triage"))
        self.registry.register(MockFailingAgent("git_forensics"))
        llm = FakeLLMProvider(responses=[self._plan_for("log_triage", "git_forensics")])

        with warnings.catch_warnings(record=True) as records:
            warnings.simplefilter("always")
            state = await self._commander(llm).investigate(incident_id)

        assert [f.agent_name for f in state.findings] == ["log_triage"]
        assert all(isinstance(f, AgentResult) for f in state.findings)
        assert _serialization_warnings(records) == []

    async def test_persisted_state_round_trips(self) -> None:
        """What was written must reload as the same typed findings."""
        state = await self._investigate(*AGENT_NAMES)
        record = self.investigation_repo.get_by_incident_id(state.incident_id)
        assert record is not None

        reloaded = InvestigationState.model_validate_json(record["state_json"])

        assert all(isinstance(f, AgentResult) for f in reloaded.findings)
        assert [f.agent_name for f in reloaded.findings] == [
            f.agent_name for f in state.findings
        ]

    async def test_serialized_shape_is_unchanged(self) -> None:
        """The API returns state.model_dump(mode="json"); keep its keys stable."""
        state = await self._investigate("log_triage")

        finding = state.model_dump(mode="json")["findings"][0]

        assert set(finding) == {
            "agent_name",
            "summary",
            "findings",
            "confidence",
            "metadata",
        }
        assert finding["agent_name"] == "log_triage"
