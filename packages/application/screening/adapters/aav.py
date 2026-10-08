"""Attribution adapter for the AAV cassette capability (section 6).

An AAV cassette is the cleanest case in the build: `AAVDesign.elements` is the
cassette laid end to end, and `AAVDesign.layout()` already gives every element
its coordinates. Each element either names a registry part id or carries a
`source` string, so the spans fall out of the design with nothing inferred.

What this adapter proves, span by span:

* An element with a `part_id` becomes a `REGISTRY_PART` span. The provenance
  assertion then looks the id up in `data/parts` and compares the bases, so the
  claim is verified rather than taken on trust. The 3' ITR is the reverse
  complement of its own registry record in a correct cassette, which the
  assertion allows explicitly.
* An element without a `part_id` is attributed from its `source` token, which
  must declare itself: `user_input:<field>` for a sequence the user supplied,
  `retrieved_template:<id>` for one the corpus supplied. The transgene coding
  sequence is normally the first of those.
* An element whose source declares nothing leaves its span uncovered, so the
  export is blocked and the message names the element and its bases. A
  transgene resolver that returns an unprefixed token is the case this catches.
"""

from __future__ import annotations

from packages.core.schemas.aav import AAVDesign
from packages.core.schemas.capability import CapabilityKind

from ..attribution import AttributedSegment, AttributedSequence, ExportSubject, SequenceOrigin
from . import REGISTRY_PART_PREFIX, classify_source

ADAPTER_NAME = "screening.adapters.aav"

#: The name the cassette carries in the subject and in every audit entry.
CASSETTE_SEQUENCE_NAME = "cassette"


def aav_subject(
    design: AAVDesign,
    *,
    validator_version: str,
    declared_provenance: list[str] | None = None,
) -> ExportSubject:
    """Build the `ExportSubject` for one composed cassette.

    `declared_provenance` defaults to the design's own `provenance`, which is
    what `DesignResult.provenance` carries. Passing it explicitly lets a caller
    screen against the exact list that will be shown to the user.
    """
    segments: list[AttributedSegment] = []
    for item in design.layout():
        element = design.elements[item.index]
        if element.part_id:
            segments.append(
                AttributedSegment(
                    start=item.start,
                    end=item.end,
                    origin=SequenceOrigin.REGISTRY_PART,
                    source=f"{REGISTRY_PART_PREFIX}{element.part_id}",
                    part_id=element.part_id,
                    detail=f"{item.role.value}: {element.name}",
                )
            )
            continue
        source = element.source or ""
        origin = classify_source(source)
        if origin is None:
            # Nothing in the design says where these bases came from, so no
            # span is emitted. The gap blocks the export and the provenance
            # assertion reports the coordinates and the bases.
            continue
        segments.append(
            AttributedSegment(
                start=item.start,
                end=item.end,
                origin=origin,
                source=source,
                detail=f"{item.role.value}: {element.name}",
            )
        )

    cassette = AttributedSequence(
        name=CASSETTE_SEQUENCE_NAME,
        sequence=design.cassette_sequence,
        segments=segments,
        role="aav_cassette",
    )
    return ExportSubject(
        capability=CapabilityKind.AAV,
        design_id=design.design_id,
        validator_version=validator_version,
        sequences=[cassette],
        declared_provenance=list(
            declared_provenance if declared_provenance is not None else design.provenance
        ),
        adapter=ADAPTER_NAME,
    )
