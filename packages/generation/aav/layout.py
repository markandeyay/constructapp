"""Linear cassette layout and the length budget table (sections 6.8 and 10.2).

AAV cassettes are linear. Section 6.8 and section 10.2 both say so explicitly,
and section 10.2 adds that reusing the circular renderer would be a visible
error to anyone in the field. Nothing in this module has a topology other than
linear, and the layout it emits carries plain start and end coordinates with no
wraparound.

The length budget table is the other half: every element, its bp, the running
total, and the remaining headroom against the limit that applies. Section 10.2
calls it the clearest artifact in the product.
"""

from __future__ import annotations

import json

from packages.core.schemas.aav import (
    AAVDesign,
    CassetteElementRole,
    LayoutElement,
    LengthBudget,
    LengthBudgetRow,
)
from packages.validation.aav.constants import AAVThresholds, DEFAULT_THRESHOLDS


def applied_thresholds(design: AAVDesign, thresholds: AAVThresholds = DEFAULT_THRESHOLDS) -> AAVThresholds:
    """The thresholds for one design, with the section 6.3 override applied."""
    return thresholds.with_packaging_limit(design.packaging_limit_bp, design.self_complementary)


def linear_layout(design: AAVDesign) -> tuple[LayoutElement, ...]:
    """Element coordinates along the linear cassette, 5' to 3'."""
    return design.layout()


def length_budget(design: AAVDesign, thresholds: AAVThresholds = DEFAULT_THRESHOLDS) -> LengthBudget:
    """Build the section 6.8 length budget table.

    `headroom_bp` on each row is the headroom that remains after that element,
    measured against the target of the band that applies to the design's
    modality, so a reader can see exactly where the budget ran out. A negative
    value is the overage.
    """
    applied = applied_thresholds(design, thresholds)
    target, soft, hard = applied.band(design.self_complementary)
    rows: list[LengthBudgetRow] = []
    running = 0
    for item in linear_layout(design):
        running += item.length_bp
        rows.append(
            LengthBudgetRow(
                index=item.index,
                role=item.role,
                name=item.name,
                part_id=item.part_id,
                source=None if item.part_id else design.elements[item.index].source,
                length_bp=item.length_bp,
                running_total_bp=running,
                headroom_bp=target - running,
            )
        )
    total = design.total_bp
    if design.self_complementary:
        basis = (
            "Self complementary design: the halved self complementary band applies, because the packaged "
            "genome is the cassette duplicated."
        )
    else:
        basis = "Single stranded design: the single stranded band applies."
    if design.packaging_limit_bp is not None:
        basis += (
            f" packaging_limit_bp was overridden to {design.packaging_limit_bp:,} bp, and the soft and hard "
            f"limits moved with it keeping the default band widths."
        )
    return LengthBudget(
        rows=rows,
        total_bp=total,
        target_bp=target,
        soft_limit_bp=soft,
        hard_limit_bp=hard,
        headroom_bp=target - total,
        self_complementary=design.self_complementary,
        limit_basis=basis,
    )


def linear_map_payload(design: AAVDesign, thresholds: AAVThresholds = DEFAULT_THRESHOLDS) -> dict[str, object]:
    """The linear map the UI renders, as a plain JSON friendly mapping.

    Coordinates are given twice: zero-based with an exclusive end, which is the
    convention everywhere else in the contract, and 1-based inclusive, which is
    what a GenBank FEATURES table and a human both read. `topology` is present
    and is always "linear", so a consumer cannot mistake this for a plasmid
    map.
    """
    applied = applied_thresholds(design, thresholds)
    target, soft, hard = applied.band(design.self_complementary)
    return {
        "design_id": design.design_id,
        "topology": "linear",
        "total_bp": design.total_bp,
        "target_bp": target,
        "soft_limit_bp": soft,
        "hard_limit_bp": hard,
        "self_complementary": design.self_complementary,
        "serotype": design.serotype,
        "target_tissue": design.target_tissue,
        "transgene_name": design.transgene_name,
        "elements": [
            {
                "index": item.index,
                "role": CassetteElementRole(item.role).value,
                "name": item.name,
                "part_id": item.part_id,
                "start": item.start,
                "end": item.end,
                "start_1based": item.start_1based,
                "end_1based": item.end_1based,
                "length_bp": item.length_bp,
                "fraction_of_cassette": round(item.length_bp / design.total_bp, 6),
            }
            for item in linear_layout(design)
        ],
    }


def linear_map_json(design: AAVDesign, thresholds: AAVThresholds = DEFAULT_THRESHOLDS) -> str:
    """`linear_map_payload` as sorted, indented JSON, so repeated runs match byte for byte."""
    return json.dumps(linear_map_payload(design, thresholds), indent=2, sort_keys=True) + "\n"
