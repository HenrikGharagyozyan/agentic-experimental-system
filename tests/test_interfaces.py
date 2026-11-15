"""Minimal fakes satisfy the Protocols (checked by mypy statically and isinstance at runtime)."""

from collections.abc import Mapping, Sequence

import pytest
from pydantic import BaseModel

from experimental_system.backends import ExecutionBackend
from experimental_system.devices import DeviceRegistry
from experimental_system.knowledge import KnowledgeBase
from experimental_system.llm import ChatMessage, LLMClient, StructuredOutputError
from experimental_system.schemas import (
    AnalysisReport,
    DeviceCommand,
    DeviceSpec,
    DeviceStatus,
    ExecutionResult,
    ExperimentPlan,
    KnowledgeFragment,
)
from factories import make_device, make_execution, make_plan, make_report


class _CannedLLM:
    """Returns a pre-built object; no inheritance from LLMClient needed."""

    def __init__(self, response: BaseModel) -> None:
        self._response = response

    def generate[T: BaseModel](self, messages: Sequence[ChatMessage], response_model: type[T]) -> T:
        if not isinstance(self._response, response_model):
            raise StructuredOutputError(f"no canned {response_model.__name__}")
        return self._response


class _ListKnowledgeBase:
    def __init__(self, fragments: list[KnowledgeFragment]) -> None:
        self._fragments = fragments

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: Mapping[str, str | int | float | bool] | None = None,
    ) -> list[KnowledgeFragment]:
        return [f for f in self._fragments if query.lower() in f.text.lower()][:top_k]


class _StaticBackend:
    @property
    def name(self) -> str:
        return "simulation"

    def device_status(self, device_ids: Sequence[str] | None = None) -> list[DeviceStatus]:
        return [DeviceStatus(device_id="test_source", state="ok")]

    def execute(self, commands: Sequence[DeviceCommand]) -> ExecutionResult:
        return make_execution()


class _DictRegistry:
    def __init__(self, devices: list[DeviceSpec]) -> None:
        self._devices = {d.device_id: d for d in devices}

    def list_devices(self) -> list[DeviceSpec]:
        return list(self._devices.values())

    def get_device(self, device_id: str) -> DeviceSpec | None:
        return self._devices.get(device_id)


def test_llm_fake_satisfies_protocol() -> None:
    llm: LLMClient = _CannedLLM(make_report())  # static check by mypy
    assert isinstance(llm, LLMClient)
    messages = [ChatMessage(role="user", content="analyse")]
    assert llm.generate(messages, AnalysisReport).decision == make_report().decision


def test_llm_fake_reports_wrong_response_model() -> None:
    llm: LLMClient = _CannedLLM(make_report())
    with pytest.raises(StructuredOutputError):
        llm.generate([], ExperimentPlan)


def test_knowledge_base_fake_satisfies_protocol() -> None:
    fragment = KnowledgeFragment(fragment_id="f1", text="Ising model energy", source="paper")
    kb: KnowledgeBase = _ListKnowledgeBase([fragment])
    assert isinstance(kb, KnowledgeBase)
    assert kb.search("ising") == [fragment]


def test_backend_fake_satisfies_protocol() -> None:
    backend: ExecutionBackend = _StaticBackend()
    assert isinstance(backend, ExecutionBackend)
    assert backend.execute([]).backend == backend.name


def test_registry_fake_satisfies_protocol() -> None:
    registry: DeviceRegistry = _DictRegistry([make_device()])
    assert isinstance(registry, DeviceRegistry)
    assert registry.get_device("test_source") == make_device()
    assert registry.get_device("unknown") is None


def test_object_without_methods_is_not_a_backend() -> None:
    assert not isinstance(object(), ExecutionBackend)
    assert not isinstance(make_plan(), DeviceRegistry)
