"""Rule Set 2 (Azimuth) in the generator: fixture, batching and honest fallback.

The regression fixture is three real Azimuth outputs produced in the container.
Tests that need Docker and the built image skip cleanly without them; the
fallback tests use an injected runner and need neither.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from packages.generation.grna import GuideRNAGenerator, azimuth
from packages.validation.grna.ontarget import RULE_SET_1_NAME

from .conftest import FIXED_TIME, make_request

FIXTURE = {
    "ACAG" + "CTGATCTCCAGATATGACCA" + "TGG" + "TTT": 0.719176,
    "TTTT" + "GCCGAGAAGTTGGGCTACGA" + "CGG" + "ACA": 0.626039,
    "GGGG" + "AAAAAAAAAAAAAAAAAAAA" + "AGG" + "GGG": 0.257333,
}


def _image_present() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        done = subprocess.run(
            ["docker", "image", "inspect", azimuth.image_name()],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0


needs_image = pytest.mark.skipif(
    not _image_present(), reason="Docker or the construct-azimuth image is not available"
)


@pytest.fixture(autouse=True)
def _fresh_cache():
    azimuth.clear_cache()
    yield
    azimuth.clear_cache()


def _result(request):
    return GuideRNAGenerator(evaluated_at=FIXED_TIME).compose(request)


@needs_image
def test_container_reproduces_the_real_azimuth_fixture() -> None:
    scores = azimuth.score_contexts(list(FIXTURE))
    for context, expected in FIXTURE.items():
        assert round(scores[context], 6) == expected


@needs_image
def test_end_to_end_names_rule_set_2_and_cites_it() -> None:
    result = _result(make_request(on_target_model="rule_set_2"))
    rows = [r for r in result.guides_returned if not r.pam_is_alternative]
    assert rows
    for row in rows:
        assert row.on_target.model_name == azimuth.RULE_SET_2_NAME
        assert "10.1038/nbt.3437" in row.on_target.citation
        assert "not a measurement" in row.on_target.disclaimer
        assert any("no confidence interval" in c for c in row.on_target.caveats)


def _fake(stdout="", stderr="", code=0):
    def run(argv, stdin_text, timeout):
        return subprocess.CompletedProcess(argv, code, stdout, stderr)

    return run


@pytest.mark.parametrize(
    "runner, category",
    [
        (_fake("", "Unable to find image 'construct-azimuth:2.0' locally", 125), "image not built"),
        (_fake(json.dumps({"error": "boom"}), "", 1), "scorer error"),
        (_fake("not json"), "scorer error"),
        (_fake(json.dumps({"scores": [0.5]})), "scorer error"),  # wrong count
        (_fake(json.dumps({"scores": ["nan"] * 1000})), "scorer error"),
    ],
)
def test_container_failures_fall_back_and_say_so(monkeypatch, runner, category) -> None:
    monkeypatch.setattr(azimuth, "_default_runner", runner)
    monkeypatch.setattr(azimuth.shutil, "which", lambda name: "/usr/bin/docker")
    result = _result(make_request(on_target_model="rule_set_2"))
    assert result.guides_returned
    for row in result.guides_returned:
        assert row.on_target.model_name.startswith(RULE_SET_1_NAME)
        assert "fallback" in row.on_target.model_name
        assert category in row.on_target.model_name
        assert "not a 2016 score" in " ".join(row.on_target.caveats)
        assert row.on_target.score is not None and row.on_target.score > 1.0  # Rule Set 1 scale


def test_missing_docker_falls_back_and_says_so(monkeypatch) -> None:
    monkeypatch.setattr(azimuth.shutil, "which", lambda name: None)
    result = _result(make_request(on_target_model="rule_set_2"))
    for row in result.guides_returned:
        assert "Docker not available" in row.on_target.model_name
        assert azimuth.RULE_SET_2_NAME in row.on_target.model_name  # says what was not used


def test_a_failure_is_not_cached(monkeypatch) -> None:
    ctx = next(iter(FIXTURE))
    monkeypatch.setattr(azimuth.shutil, "which", lambda name: None)
    with pytest.raises(azimuth.AzimuthUnavailable):
        azimuth.score_contexts([ctx])
    monkeypatch.setattr(azimuth.shutil, "which", lambda name: "/usr/bin/docker")
    got = azimuth.score_contexts([ctx], runner=_fake(json.dumps({"scores": [0.25]})))
    assert got == {ctx: 0.25}


def test_one_container_call_per_request(monkeypatch) -> None:
    calls = []

    def run(argv, stdin_text, timeout):
        calls.append(json.loads(stdin_text))
        return subprocess.CompletedProcess(
            argv, 0, json.dumps({"scores": [0.5] * len(json.loads(stdin_text))}), ""
        )

    monkeypatch.setattr(azimuth, "_default_runner", run)
    monkeypatch.setattr(azimuth.shutil, "which", lambda name: "/usr/bin/docker")
    result = _result(make_request(on_target_model="rule_set_2"))
    assert len(calls) == 1
    assert len(calls[0]) == len(set(calls[0]))
    assert result.guides_returned[0].on_target.score == 0.5


def test_rule_set_1_stays_the_default_and_never_touches_docker(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise AssertionError("docker must not be consulted for Rule Set 1")

    monkeypatch.setattr(azimuth, "_default_runner", boom)
    monkeypatch.setattr(azimuth.shutil, "which", boom)
    result = _result(make_request())
    assert all(r.on_target.model_name == RULE_SET_1_NAME for r in result.guides_returned)


def test_non_ngg_context_is_not_sent_to_the_container() -> None:
    assert not azimuth.context_is_scorable("A" * 30)
    assert not azimuth.context_is_scorable(None)
    assert azimuth.context_is_scorable(next(iter(FIXTURE)))


def test_out_of_domain_stays_out_of_domain(monkeypatch) -> None:
    monkeypatch.setattr(azimuth.shutil, "which", lambda name: None)
    result = _result(make_request(on_target_model="rule_set_2", expression_system="t7_in_vitro"))
    for row in result.guides_returned:
        assert row.on_target.score is None
        assert row.on_target.status == "out_of_domain"
