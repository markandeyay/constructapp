"""Attribution adapter for the plasmid capability (section 11.1).

This is the fourth adapter and the only one whose spans are verified against the
record they name rather than taken on trust. That difference is worth stating
plainly, because it is the difference between the gate recording an attribution
and the gate checking one.

The other three capabilities compose from the curated registry plus the user's
own submitted sequence. A registry span is compared against `data/parts` base for
base; a user input span has nothing external to compare against, because the
bases are the user's own and the record of them is the request. Neither needs
coordinates.

A plasmid candidate is different. It is grounded in a retrieved corpus template,
so its bases have an external record, and that record is kept: the corpus retains
the full sequence of every plasmid it holds. So a plasmid span carries the
coordinates of its bases inside that template, and `assert_provenance` fetches
the named record and compares. A span saying "these bases came from template X"
becomes evidence only once someone has fetched X and looked, and here someone
does.

What this adapter proves, span by span:

* Each `SequenceSpan` the generator recorded becomes one `RETRIEVED_TEMPLATE`
  segment carrying the template id and the source coordinates, so the assertion
  can locate the bases in the record and compare them.
* Every span's source token must appear in the declared provenance, which the
  caller builds from the design's separately stored template ids. The two fields
  are written independently, so a span naming a template the record does not list
  is caught rather than self certified.
* Bases no span covers stay uncovered, so the export is blocked and the message
  names the coordinates. This is the case that matters most here: a generator
  that splices in sequence of its own invention records no span for those bases,
  so model written sequence cannot reach an export. A design stored before spans
  were recorded at all has no spans, covers nothing, and is likewise refused
  rather than grandfathered.
"""

from __future__ import annotations

from collections.abc import Sequence

from packages.core.schemas.capability import CapabilityKind
from packages.core.schemas.models import AnnotatedSequence, SequenceSpan

from ..attribution import AttributedSegment, AttributedSequence, ExportSubject, SequenceOrigin
from . import RETRIEVED_TEMPLATE_PREFIXES

ADAPTER_NAME = "screening.adapters.plasmid"

#: The name the candidate carries in the subject and in every audit entry.
PLASMID_SEQUENCE_NAME = "plasmid"

#: The token prefix a plasmid span's source uses. Taken from the shared list
#: rather than written again here, so this adapter and `classify_source` cannot
#: drift apart and start disagreeing about what a template token looks like.
TEMPLATE_PREFIX = RETRIEVED_TEMPLATE_PREFIXES[0]


def template_token(template_id: str) -> str:
    """The provenance token for a template id, in one place so it cannot drift."""
    return f"{TEMPLATE_PREFIX}{template_id}"


def declared_provenance_for(template_ids: Sequence[str]) -> list[str]:
    """The provenance tokens a design's stored template ids imply.

    Built from `template_ids` and deliberately not from the spans. The gate
    requires every span's source to appear in the declared provenance, and that
    check is only worth running if the two sides come from different places: a
    list derived from the spans would agree with them by construction and would
    catch nothing.
    """
    return [template_token(template_id) for template_id in template_ids]


def plasmid_subject(
    annotated_sequence: AnnotatedSequence,
    *,
    design_id: str,
    validator_version: str,
    sequence_spans: Sequence[SequenceSpan],
    template_ids: Sequence[str],
) -> ExportSubject:
    """Build the `ExportSubject` for one stored plasmid design.

    Takes the stored fields explicitly rather than a `DesignRecord`, so this
    stays a function of the data and not of the persistence layer, and so a
    caller holding the same data from anywhere else can screen it.
    """
    segments = [
        AttributedSegment(
            start=span.start,
            end=span.end,
            origin=SequenceOrigin.RETRIEVED_TEMPLATE,
            source=span.source,
            template_id=span.source_id,
            source_start=span.source_start,
            source_end=span.source_end,
            detail=(
                f"bases ({span.source_start}, {span.source_end}) of template {span.source_id}"
            ),
        )
        for span in sequence_spans
    ]

    candidate = AttributedSequence(
        name=PLASMID_SEQUENCE_NAME,
        sequence=annotated_sequence.sequence,
        segments=segments,
        role="plasmid",
    )
    return ExportSubject(
        capability=CapabilityKind.PLASMID,
        design_id=design_id,
        validator_version=validator_version,
        sequences=[candidate],
        declared_provenance=declared_provenance_for(template_ids),
        adapter=ADAPTER_NAME,
    )


__all__ = [
    "ADAPTER_NAME",
    "PLASMID_SEQUENCE_NAME",
    "TEMPLATE_PREFIX",
    "declared_provenance_for",
    "plasmid_subject",
    "template_token",
]
