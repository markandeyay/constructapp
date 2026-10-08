from __future__ import annotations

from pathlib import Path

import pytest

import services.api.routes as routes
from packages.core import capability_registry
from packages.core.capability_registry import (
    CAPABILITY_REGISTRY,
    PLASMID_SPEC,
    CapabilitySpec,
    get_capability,
    list_capabilities,
    resolve_reference,
)
from packages.core.schemas.capability import CapabilityKind

# Section 13.3, reproduced character for character.
REGION_LINES = [
    "# ==== WP-03: AAV. Only WP-03 writes here. ====",
    "# ==== /WP-03 ====",
    "# ==== WP-04: assembly. Only WP-04 writes here. ====",
    "# ==== /WP-04 ====",
    "# ==== WP-05: guide RNA. Only WP-05 writes here. ====",
    "# ==== /WP-05 ====",
]


def stripped_lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize("module", [capability_registry, routes])
def test_reserved_regions_are_present_once_and_in_order(module: object) -> None:
    lines = stripped_lines(Path(module.__file__))  # type: ignore[attr-defined]
    positions = []
    for expected in REGION_LINES:
        assert lines.count(expected) == 1, expected
        positions.append(lines.index(expected))
    assert positions == sorted(positions)


def test_registry_lists_plasmid_and_leaves_the_other_kinds_to_their_packages() -> None:
    assert CAPABILITY_REGISTRY[CapabilityKind.PLASMID] is PLASMID_SPEC
    for kind, spec in CAPABILITY_REGISTRY.items():
        assert spec.kind == kind
    assert [spec.kind for spec in list_capabilities()][0] == CapabilityKind.PLASMID


def test_get_capability_accepts_enum_or_string_and_fails_loudly() -> None:
    assert get_capability("plasmid") is PLASMID_SPEC
    assert get_capability(CapabilityKind.PLASMID) is PLASMID_SPEC
    unregistered = [kind for kind in CapabilityKind if kind not in CAPABILITY_REGISTRY]
    for kind in unregistered:
        with pytest.raises(KeyError, match="not registered"):
            get_capability(kind)
    with pytest.raises(KeyError, match="not registered"):
        get_capability("not_a_capability")


def test_plasmid_spec_references_resolve_to_real_code() -> None:
    for reference in (PLASMID_SPEC.request_schema, PLASMID_SPEC.result_schema, PLASMID_SPEC.generator):
        assert reference is not None
        assert resolve_reference(reference) is not None


def test_resolve_reference_rejects_malformed_references() -> None:
    for bad in ("no_colon", ":attribute", "module:"):
        with pytest.raises(ValueError):
            resolve_reference(bad)


def test_capability_spec_rejects_unknown_fields_and_blank_labels() -> None:
    with pytest.raises(ValueError):
        CapabilitySpec(kind=CapabilityKind.AAV, label="", description="d")
    with pytest.raises(ValueError):
        CapabilitySpec(kind=CapabilityKind.AAV, label="AAV", description="d", surprise=1)


def test_router_block_is_empty_until_capabilities_register() -> None:
    assert all(isinstance(item, routes.RouterInclude) for item in routes.CAPABILITY_ROUTERS)


class _App:
    def __init__(self) -> None:
        self.included: list[tuple[object, str]] = []

    def include_router(self, router: object, prefix: str = "") -> None:
        self.included.append((router, prefix))


def test_include_capability_routers_includes_each_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = PLASMID_SPEC
    monkeypatch.setattr(routes, "CAPABILITY_ROUTERS", (routes.RouterInclude("aav", "packages.core.capability_registry:PLASMID_SPEC", "/x"),))
    app = _App()
    assert routes.include_capability_routers(app) == ["aav"]
    assert app.included == [(sentinel, "/x")]


def test_load_router_rejects_malformed_references() -> None:
    with pytest.raises(ValueError):
        routes.load_router(routes.RouterInclude("aav", "missing_colon"))


def test_validator_factory_raises_when_a_capability_registers_no_validator() -> None:
    unregistered = CapabilitySpec(kind=CapabilityKind.AAV, label="AAV", description="d")
    with pytest.raises(LookupError, match="registers no validator"):
        unregistered.validator_factory()
    assert unregistered.design_model is None


def test_plasmid_registers_the_adapter_so_the_gold_runner_can_resolve_it() -> None:
    validator = PLASMID_SPEC.validator_factory()
    assert validator.kind == CapabilityKind.PLASMID
    assert callable(validator.validate)
    assert PLASMID_SPEC.design_model is resolve_reference("packages.core.schemas.plasmid:PlasmidDesign")


def test_validator_factory_and_design_model_for_the_gold_runner() -> None:
    spec = CapabilitySpec(
        kind=CapabilityKind.AAV,
        label="AAV",
        description="d",
        validator_ref="packages.core.schemas.capability:CheckResult",
        design_model_ref="packages.core.schemas.capability:CheckResult",
    )
    assert spec.design_model is resolve_reference("packages.core.schemas.capability:CheckResult")
    assert callable(spec.validator_factory)
