"""Doench 2016 on-target model (Rule Set 2, "Azimuth"), run in a container.

This is a GENERATOR side recommendation, never a validator check. Hard
constraint 3.3.3 puts a model in the generator, as a recommendation with its
uncertainty surfaced. Nothing here is reachable from `GuideRNAValidator`, and no
validator check reads these scores.

Why a container: Azimuth 2.0 is Python 2 code whose model pickles only load on
scikit-learn 0.17.1. That cannot be installed beside the rest of this project,
but it runs fine in `docker/azimuth/Dockerfile`, which pins the whole stack.
The container is deliberately dumb: it reads a JSON list of 30-mers and returns
the scores Azimuth computed. Every policy decision lives in this module.

The model is OPTIONAL and degrades honestly (specification 8.4 and the section
16 claim register). A request asks for it with `on_target_model="rule_set_2"`.
If Docker is missing, the image is not built, the container errors, or its
output is malformed, the guide is scored with Rule Set 1 instead and the score's
model name SAYS SO. A Rule Set 1 number is never presented as a 2016 score, and
no number is ever filled in when the container did not produce one.

Nothing in this file is a coefficient. The model weights live inside the
Azimuth package in the image; none is transcribed here.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable, Sequence

from packages.core.schemas.grna import OnTargetScore
from packages.validation.grna.ontarget import RULE_SET_1_NAME

RULE_SET_2_NAME = "Rule Set 2 (Azimuth) sgRNA on-target activity model"

RULE_SET_2_CITATION = (
    "Doench JG, Fusi N, Sullender M, et al. Optimized sgRNA design to maximize activity and "
    "minimize off-target effects of CRISPR-Cas9. Nat Biotechnol 2016;34(2):184-191, "
    "doi:10.1038/nbt.3437, PMID 26780180. Run through the authors' Azimuth 2.0 package "
    "(Microsoft Research, PyPI azimuth==2.0, model_comparison.predict) in the container built "
    "from docker/azimuth/Dockerfile. No coefficient is transcribed in this repository."
)

RULE_SET_2_DOMAIN = (
    "SpCas9, NGG PAM, 20 nt spacer, 30 nt context required (4 nt 5' flank, 20 nt spacer, "
    "3 nt PAM, 3 nt 3' flank; Azimuth rejects any input whose PAM is not NGG). Trained on "
    "measured knockout activity of SpCas9 guides in mammalian cell lines. Not applicable to "
    "SaCas9 or Cas12a, to in-vitro-transcribed guides, to non-mammalian or cell-free systems, "
    "or to transcriptional activation or interference."
)

RULE_SET_2_SCALE = (
    "Azimuth output, roughly 0 to 1, higher is more active. Not the 0 to 100 scale of Rule "
    "Set 1 and not comparable to it."
)

RULE_SET_2_DISCLAIMER = (
    "Predicted activity, not a measurement. Confirm at the bench before relying on it."
)

#: Stated once, attached to every Rule Set 2 score, because section 3.3.3 wants
#: the uncertainty surfaced with the recommendation. Azimuth returns a point
#: estimate with no interval, so the honest statement is that none exists here.
RULE_SET_2_UNCERTAINTY = (
    "Azimuth returns a single point estimate with no confidence interval, so no per guide "
    "uncertainty is available. Predicted activity correlates only moderately with measured "
    "activity even on the data the model was built for, so use the number to rank guides "
    "against each other rather than as an expected cutting efficiency. The model is an opaque "
    "tree ensemble, so no per feature reasoning is shown for this score."
)

DEFAULT_IMAGE = "construct-azimuth:2.0"
IMAGE_ENV_VAR = "CONSTRUCT_AZIMUTH_IMAGE"
DEFAULT_TIMEOUT_SECONDS = 120.0

CONTEXT_LENGTH = 30

#: Runner signature: `(argv, stdin_text, timeout) -> CompletedProcess`. Injectable
#: so tests exercise every failure path without Docker.
Runner = Callable[[list, str, float], "subprocess.CompletedProcess[str]"]


class AzimuthUnavailable(Exception):
    """The container could not produce scores. `category` is short and goes in the model name."""

    def __init__(self, category: str, detail: str):
        super().__init__(f"{category}: {detail}")
        self.category = category
        self.detail = detail


def _default_runner(argv: list, stdin_text: str, timeout: float):
    return subprocess.run(
        argv, input=stdin_text, capture_output=True, text=True, timeout=timeout, check=False
    )


def image_name() -> str:
    return os.environ.get(IMAGE_ENV_VAR) or DEFAULT_IMAGE


# Deterministic model, so a context never needs scoring twice in one process.
# Only successful container results are cached; a failure is never remembered,
# so building the image mid session starts working without a restart.
_CACHE: dict = {}


def clear_cache() -> None:
    _CACHE.clear()


def context_is_scorable(context) -> bool:
    """Azimuth requires 30 nt of ACGT with GG at 0-based positions 25 and 26."""
    return (
        context is not None
        and len(context) == CONTEXT_LENGTH
        and set(context) <= set("ACGT")
        and context[25:27] == "GG"
    )


def score_contexts(
    contexts: Sequence[str],
    *,
    runner=None,
    which: Callable | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    """Score distinct 30-mers with one container run. Raises `AzimuthUnavailable`.

    One container start covers the whole batch. Starting Python 2 and loading
    the pickles dominates the cost, so scoring per guide in a loop would be
    far slower than scoring them together.
    """
    unique = sorted(set(contexts))
    for context in unique:
        if not context_is_scorable(context):
            raise ValueError(f"not a scorable Azimuth context: {context!r}")
    todo = [c for c in unique if c not in _CACHE]
    if todo:
        if (which or shutil.which)("docker") is None:
            raise AzimuthUnavailable("Docker not available", "the docker executable was not found")
        # --pull never: a missing image must be reported, not silently downloaded
        # from a registry. --network none: the scorer needs no network.
        argv = ["docker", "run", "--rm", "-i", "--pull", "never", "--network", "none", image_name()]
        try:
            proc = (runner or _default_runner)(argv, json.dumps(todo), timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AzimuthUnavailable("scorer error", f"{type(exc).__name__}: {exc}") from exc
        if proc.returncode != 0:
            err = (proc.stderr or "") + " " + (proc.stdout or "")
            if "Unable to find image" in err or "No such image" in err or "pull access denied" in err:
                raise AzimuthUnavailable(
                    "scorer image not built",
                    f"image {image_name()} is absent; build it with "
                    "`docker build -t construct-azimuth:2.0 docker/azimuth`",
                )
            raise AzimuthUnavailable(
                "scorer error", f"container exited {proc.returncode}: {err.strip()[:300]}"
            )
        try:
            payload = json.loads(proc.stdout)
            values = payload["scores"]
            if not isinstance(values, list) or len(values) != len(todo):
                raise ValueError("score count does not match the request")
            parsed = [float(v) for v in values]
            if not all(math.isfinite(v) for v in parsed):
                raise ValueError("non finite score")
        except (ValueError, KeyError, TypeError) as exc:
            raise AzimuthUnavailable("scorer error", f"malformed container output: {exc}") from exc
        _CACHE.update(zip(todo, parsed))
    return {c: _CACHE[c] for c in unique}


@dataclass(frozen=True)
class Rule2Outcome:
    """Batch result: scores by context, or the reason none are available."""

    scores: dict
    unavailable: "AzimuthUnavailable | None" = None


def batch_score(contexts: Sequence, **kwargs) -> Rule2Outcome:
    """Score every scorable context in one call; never raises."""
    scorable = [c for c in contexts if context_is_scorable(c)]
    if not scorable:
        return Rule2Outcome({})
    try:
        return Rule2Outcome(score_contexts(scorable, **kwargs))
    except AzimuthUnavailable as exc:
        return Rule2Outcome({}, exc)


def apply_rule_set_2(rule1: OnTargetScore, context, outcome: Rule2Outcome) -> OnTargetScore:
    """Turn the Rule Set 1 result into the Rule Set 2 result, or an honest fallback.

    `rule1` already carries the shared domain decision (SpCas9, NGG, mammalian
    knockout), so an out of domain request stays out of domain and keeps its
    reasons. In every fallback the model name states that Rule Set 2 was
    requested and not used, so the Rule Set 1 number cannot be read as a 2016
    score.
    """
    requested = f"{RULE_SET_2_NAME} requested"
    if rule1.status == "out_of_domain":
        return rule1.model_copy(
            update={
                "caveats": [
                    f"{requested}. It shares Rule Set 1's validity domain, so no score from "
                    "either model is returned."
                ]
                + list(rule1.caveats)
            }
        )
    score = outcome.scores.get(context) if context is not None else None
    if score is not None:
        # The shared domain caveats (activation intent, host context) are worded
        # with the Rule Set 1 name; they apply equally here, so re-name them.
        carried = [c.replace(RULE_SET_1_NAME, RULE_SET_2_NAME) for c in rule1.caveats]
        return OnTargetScore(
            model_name=RULE_SET_2_NAME,
            model_kind="published_model",
            citation=RULE_SET_2_CITATION,
            validity_domain=RULE_SET_2_DOMAIN,
            status="in_domain_with_caveat",
            score=round(score, 6),
            score_scale=RULE_SET_2_SCALE,
            caveats=carried + [RULE_SET_2_UNCERTAINTY],
            reasoning=[],
            disclaimer=RULE_SET_2_DISCLAIMER,
        )
    if outcome.unavailable is not None:
        category = outcome.unavailable.category
        why = f"{requested} but unavailable ({outcome.unavailable.detail})."
    else:
        category = "context not scorable by Rule Set 2"
        why = (
            f"{requested} but this guide's 30 nt context is not NGG with only A, C, G and T, "
            "which Azimuth requires."
        )
    return rule1.model_copy(
        update={
            "model_name": f"{RULE_SET_1_NAME} (fallback, {RULE_SET_2_NAME} not used: {category})",
            "status": "in_domain_with_caveat",
            "caveats": [why + " This is the 2014 Rule Set 1 score, not a 2016 score."]
            + list(rule1.caveats),
        }
    )
