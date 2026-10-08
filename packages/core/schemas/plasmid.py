"""The plasmid capability's design model (section 5.3, section 5.1).

The plasmid capability pre-dates the shared contract. Its validator, the
deterministic constraint engine in `packages.validation.engine`, takes two
arguments (`AnnotatedSequence` and `DesignSpec`) rather than the single
`design` the `CapabilityValidator` protocol passes. `PlasmidDesign` is that one
object: it carries exactly the two inputs the engine already needs, so the
adapter in `packages.validation.plasmid.validator` can satisfy the protocol
without the engine changing.

This is also the model a gold case `input` is parsed into, which is why the
field names are the same ones the curated records in
`data/eval/validation/curated_known_*.jsonl` already use: a case input is the
two blocks of a curated record, unchanged.
"""

from __future__ import annotations

from pydantic import Field

from .models import AnnotatedSequence, DesignSpec, SchemaModel


class PlasmidDesign(SchemaModel):
    """One plasmid candidate, ready to validate.

    `provenance` is optional and records where the bases came from (section 5.4
    rule 5). When it is empty the adapter derives the honest default, which for
    a sequence handed straight to the validator is `user_input:<field name>`.
    `design_id` is likewise optional, so a gold case does not have to invent one.
    """

    design_spec: DesignSpec
    annotated_sequence: AnnotatedSequence
    design_id: str | None = Field(default=None)
    provenance: list[str] = Field(default_factory=list)
