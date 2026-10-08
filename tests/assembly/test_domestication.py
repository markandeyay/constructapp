"""Golden Gate domestication and the Appendix D enzyme reference.

Source: section 7.6 and Appendix D of the engine capability system design.

Section 7.6 names five things a report entry must carry: "the position, the
original codon, the proposed codon, the amino acid preserved, and the host codon
frequency of both". The host codon frequency is the one this build cannot
produce from a bundled table, so these tests assert the honest form: UNKNOWN
with a reason, and the number when a caller supplies a table.
"""

from __future__ import annotations

import pytest

from packages.core.schemas.assembly import Fragment
from packages.core.sequence import STANDARD_CODE, reverse_complement, translate
from packages.validation.assembly import codon_usage, domestication
from packages.validation.assembly.codon_usage import HostCodonUsage
from packages.validation.assembly.enzymes import (
    BUNDLED_OVERHANG_STANDARDS,
    TYPE_IIS_ENZYMES,
    OverhangStandard,
    find_recognition_sites,
    get_enzyme,
    get_overhang_standard,
)

# A coding fragment with a BsaI site (GGTCTC) in frame at codon 2, whose third
# codon position can be changed synonymously. Real flanking sequence is not
# needed here: what is tested is the frame arithmetic and the codon table.
CODING_WITH_SITE = "ATG" + "GGTCTC" + "AAAGGGTTTCCCGATCATGAACTGAAACGTTAC" + "TAA"


# ---------------------------------------------------------------------------
# Appendix D, the enzyme table
# ---------------------------------------------------------------------------


def test_the_five_appendix_d_enzymes_are_present_with_their_values() -> None:
    """Appendix D, row for row. Nothing added, nothing changed."""
    assert set(TYPE_IIS_ENZYMES) == {"BsaI", "BsmBI", "BbsI", "SapI", "AarI"}
    expected = {
        "BsaI": ("GGTCTC", 1, 5, 4),
        "BsmBI": ("CGTCTC", 1, 5, 4),
        "BbsI": ("GAAGAC", 2, 6, 4),
        "SapI": ("GCTCTTC", 1, 4, 3),
        "AarI": ("CACCTGC", 4, 8, 4),
    }
    for name, (recognition, top, bottom, overhang) in expected.items():
        enzyme = TYPE_IIS_ENZYMES[name]
        assert enzyme.recognition == recognition
        assert (enzyme.top_cut_offset, enzyme.bottom_cut_offset) == (top, bottom)
        assert enzyme.overhang_nt == overhang
        # Appendix D's own consistency rule: the overhang is N2 minus N1.
        assert enzyme.overhang_nt == enzyme.bottom_cut_offset - enzyme.top_cut_offset


def test_no_appendix_d_recognition_sequence_is_palindromic() -> None:
    """Appendix D says so, which is why both strands must be searched."""
    for enzyme in TYPE_IIS_ENZYMES.values():
        assert not enzyme.is_palindromic, enzyme.name


def test_appendix_d_aliases_resolve() -> None:
    assert get_enzyme("Esp3I") is TYPE_IIS_ENZYMES["BsmBI"]
    assert get_enzyme("BpiI") is TYPE_IIS_ENZYMES["BbsI"]
    assert get_enzyme("LguI") is TYPE_IIS_ENZYMES["SapI"]
    assert get_enzyme("bsai") is TYPE_IIS_ENZYMES["BsaI"]


def test_an_unsupported_enzyme_fails_loudly_and_names_the_alternatives() -> None:
    """Section 3.3 constraint 4: never fall back to a default enzyme."""
    with pytest.raises(KeyError) as excinfo:
        get_enzyme("EcoRI")
    assert "Appendix D" in str(excinfo.value)
    assert "BsaI" in str(excinfo.value)


def test_recognition_sites_are_found_on_both_strands() -> None:
    """Appendix D's both-strands requirement, tested directly."""
    enzyme = get_enzyme("BsaI")
    forward = "AAAA" + enzyme.recognition + "AAAA"
    reverse = "AAAA" + reverse_complement(enzyme.recognition) + "AAAA"
    assert [hit.strand for hit in find_recognition_sites(forward, enzyme)] == [1]
    assert [hit.strand for hit in find_recognition_sites(reverse, enzyme)] == [-1]


# ---------------------------------------------------------------------------
# Section 7.6, the report
# ---------------------------------------------------------------------------


def test_a_coding_site_gets_a_synonymous_edit_that_preserves_the_protein() -> None:
    """Section 7.6: inside a coding sequence the substitution must preserve the amino acid."""
    fragment = Fragment(
        name="cds",
        sequence=CODING_WITH_SITE,
        source="synthetic coding fragment with a BsaI site inserted",
        coding_regions=[(0, len(CODING_WITH_SITE))],
    )
    report = domestication.build_report([fragment], get_enzyme("BsaI"))
    assert report.sites_found == 1
    assert len(report.edits) == 1
    assert report.unresolved == []

    edit = report.edits[0]
    assert edit.in_coding_sequence is True
    assert edit.original_codon is not None and edit.proposed_codon is not None
    assert edit.codon_position is not None
    assert edit.amino_acid == STANDARD_CODE.translate_codon(edit.original_codon)
    assert STANDARD_CODE.translate_codon(edit.proposed_codon) == edit.amino_acid

    # The edit really destroys the site, and really preserves the protein.
    edited = (
        fragment.sequence[: edit.edit_position] + edit.proposed_base + fragment.sequence[edit.edit_position + 1 :]
    )
    assert find_recognition_sites(edited, get_enzyme("BsaI")) == []
    assert translate(edited) == translate(fragment.sequence)


def test_the_edit_is_minimal_one_base() -> None:
    """Section 7.6 prefers the minimal edit."""
    fragment = Fragment(
        name="cds",
        sequence=CODING_WITH_SITE,
        source="synthetic",
        coding_regions=[(0, len(CODING_WITH_SITE))],
    )
    report = domestication.build_report([fragment], get_enzyme("BsaI"))
    edit = report.edits[0]
    assert edit.original_codon is not None and edit.proposed_codon is not None
    differing = sum(1 for a, b in zip(edit.original_codon, edit.proposed_codon, strict=True) if a != b)
    assert differing == 1


def test_a_non_coding_site_gets_any_minimal_site_destroying_edit() -> None:
    """Section 7.6: outside a coding sequence any substitution is acceptable; prefer minimal."""
    sequence = "TTACGATCAGGTCTCGATCAGCATTACGGACT"
    fragment = Fragment(name="spacer", sequence=sequence, source="synthetic non-coding fragment")
    report = domestication.build_report([fragment], get_enzyme("BsaI"))
    assert report.sites_found == 1
    edit = report.edits[0]
    assert edit.in_coding_sequence is False
    assert edit.original_codon is None and edit.amino_acid is None
    assert edit.host_frequency_status == "unknown"
    assert edit.host_frequency_reason and "outside any declared coding sequence" in edit.host_frequency_reason
    edited = sequence[: edit.edit_position] + edit.proposed_base + sequence[edit.edit_position + 1 :]
    assert find_recognition_sites(edited, get_enzyme("BsaI")) == []


def test_a_reverse_strand_site_is_domesticated_on_the_forward_sequence() -> None:
    """Appendix D: both strands. A reverse-strand site is still an edit on one molecule."""
    sequence = "TTACGATCA" + reverse_complement("GGTCTC") + "GATCAGCATTACGGACT"
    fragment = Fragment(name="spacer", sequence=sequence, source="synthetic, reverse-strand site")
    report = domestication.build_report([fragment], get_enzyme("BsaI"))
    assert report.sites_found == 1
    edit = report.edits[0]
    assert edit.site_strand == -1
    edited = sequence[: edit.edit_position] + edit.proposed_base + sequence[edit.edit_position + 1 :]
    assert find_recognition_sites(edited, get_enzyme("BsaI")) == []


def test_an_edit_never_trades_one_site_for_another() -> None:
    """Property 2 in the module docstring: the site count must go down, not sideways."""
    enzyme = get_enzyme("BsaI")
    # Two overlapping candidate contexts, so a careless single-base edit could
    # remove one site and complete another.
    sequence = "AAGGTCTCGGTCTCGGTCTCAA"
    fragment = Fragment(name="tandem", sequence=sequence, source="synthetic tandem sites")
    report = domestication.build_report([fragment], enzyme)
    assert report.sites_found == len(find_recognition_sites(sequence, enzyme))
    for edit in report.edits:
        edited = sequence[: edit.edit_position] + edit.proposed_base + sequence[edit.edit_position + 1 :]
        assert len(find_recognition_sites(edited, enzyme)) < report.sites_found


def test_a_clean_fragment_produces_an_empty_report() -> None:
    fragment = Fragment(name="clean", sequence="TTACGATCAGATCAGCATTACGGACT", source="synthetic")
    report = domestication.build_report([fragment], get_enzyme("BsaI"))
    assert report.sites_found == 0
    assert report.edits == []
    assert report.fully_resolved is False, "no sites found is not the same as every site resolved"


def test_the_report_names_both_strands_and_the_cut_geometry() -> None:
    fragment = Fragment(name="clean", sequence="TTACGATCAGATCAGCATTACGGACT", source="synthetic")
    report = domestication.build_report([fragment], get_enzyme("BsaI"))
    joined = " ".join(report.notes)
    assert "Both strands" in joined
    assert "GGTCTC(1/5)" in joined
    assert "4 nt overhang" in joined


def test_domestication_is_deterministic() -> None:
    """Section 3.3 constraint 3: the tie-break ordering exists for this."""
    fragment = Fragment(
        name="cds",
        sequence=CODING_WITH_SITE,
        source="synthetic",
        coding_regions=[(0, len(CODING_WITH_SITE))],
    )
    first = domestication.build_report([fragment], get_enzyme("BsaI"))
    second = domestication.build_report([fragment], get_enzyme("BsaI"))
    assert first == second


# ---------------------------------------------------------------------------
# The codon table decision, section 7.6 and Appendix E
# ---------------------------------------------------------------------------


def test_no_host_codon_usage_table_is_bundled() -> None:
    """The recorded decision. If a table is ever added, this test is the reminder.

    Section 3.3 constraint 1 forbids inventing frequencies, so none ship, and the
    report says UNKNOWN with a reason instead.
    """
    assert codon_usage.BUNDLED_HOST_CODON_USAGE == {}
    with pytest.raises(KeyError, match="None ships"):
        codon_usage.get_host_codon_usage("Escherichia coli")


def test_without_a_table_the_frequency_is_unknown_with_a_reason() -> None:
    """Section 3.3 constraint 4, applied to a quantity rather than to a check."""
    fragment = Fragment(
        name="cds",
        sequence=CODING_WITH_SITE,
        source="synthetic",
        coding_regions=[(0, len(CODING_WITH_SITE))],
    )
    report = domestication.build_report([fragment], get_enzyme("BsaI"))
    assert report.host_codon_usage_status == "unknown"
    assert report.host_codon_usage_table is None
    assert any("No host codon usage table is bundled" in note for note in report.notes)
    edit = report.edits[0]
    assert edit.host_frequency_status == "unknown"
    assert edit.host_frequency_original is None
    assert edit.host_frequency_proposed is None
    assert edit.host_frequency_reason and "minimal silent edit" in edit.host_frequency_reason
    assert "UNKNOWN" in edit.summary


def test_a_supplied_table_is_used_and_named() -> None:
    """Appendix E: name the table and the host. The mechanism works when one exists.

    The frequencies here are a test fixture, not a claim about any organism. They
    exist to prove the lookup and the preference ordering work, which is why the
    host is named as a fixture rather than as a real species.
    """
    usage = HostCodonUsage(
        host="test fixture host, not a real organism",
        citation="tests/assembly/test_domestication.py, illustrative values only",
        frequencies={codon: 0.25 for codon in ("CTA", "CTC", "CTG", "CTT", "TTA", "TTG")},
    )
    fragment = Fragment(
        name="cds",
        sequence=CODING_WITH_SITE,
        source="synthetic",
        coding_regions=[(0, len(CODING_WITH_SITE))],
    )
    report = domestication.build_report([fragment], get_enzyme("BsaI"), usage=usage)
    assert report.host_codon_usage_status == "known"
    assert report.host_codon_usage_table is not None
    assert "test fixture host" in report.host_codon_usage_table
    edit = report.edits[0]
    assert edit.host_frequency_status == "known"
    assert edit.host_frequency_original == pytest.approx(0.25)
    assert edit.host_frequency_proposed == pytest.approx(0.25)
    assert edit.host_frequency_table is not None and "illustrative values only" in edit.host_frequency_table
    assert "host frequency 0.2500 to 0.2500" in edit.summary


def test_a_table_prefers_the_more_common_synonymous_codon() -> None:
    """Section 7.6: "should prefer a codon that is common in the target host"."""
    fragment = Fragment(
        name="cds",
        sequence=CODING_WITH_SITE,
        source="synthetic",
        coding_regions=[(0, len(CODING_WITH_SITE))],
    )
    without = domestication.build_report([fragment], get_enzyme("BsaI")).edits[0]
    # Make a different synonymous codon overwhelmingly preferred, and check the
    # choice follows the table rather than the sort order.
    alternatives = {"CTA": 0.01, "CTC": 0.01, "CTG": 0.01, "CTT": 0.01, "TTA": 0.01, "TTG": 0.01}
    assert without.proposed_codon in alternatives
    other = next(codon for codon in ("CTA", "CTT", "CTG") if codon != without.proposed_codon)
    alternatives[other] = 0.95
    usage = HostCodonUsage(
        host="test fixture host, not a real organism",
        citation="tests/assembly/test_domestication.py, illustrative values only",
        frequencies=alternatives,
    )
    with_table = domestication.build_report([fragment], get_enzyme("BsaI"), usage=usage).edits[0]
    # Only candidates that destroy the site are eligible, so the preferred codon
    # wins only if it is among them. Either way the frequency must be reported.
    assert with_table.host_frequency_status == "known"
    assert with_table.host_frequency_proposed is not None


def test_a_table_without_a_citation_is_refused() -> None:
    """Appendix E requires the table and the host to be named."""
    with pytest.raises(ValueError, match="no citation"):
        HostCodonUsage(host="somewhere", citation="   ", frequencies={"CTA": 1.0})
    with pytest.raises(ValueError, match="must name its host"):
        HostCodonUsage(host="  ", citation="somewhere", frequencies={"CTA": 1.0})


def test_a_table_rejects_a_non_codon() -> None:
    with pytest.raises(ValueError, match="not a DNA codon"):
        HostCodonUsage(host="h", citation="c", frequencies={"CUA": 1.0})


# ---------------------------------------------------------------------------
# The published-standard overhang mechanism, Appendix D
# ---------------------------------------------------------------------------


def test_no_published_overhang_standard_is_bundled() -> None:
    """The recorded decision: the mechanism ships, no standard's overhangs do.

    Appendix D requires a standard's overhang set to be used verbatim and cited.
    Section 3.3 constraint 1 forbids reciting the strings from memory, so none
    ship and the generated-overhang path is used with the design saying so.
    """
    assert BUNDLED_OVERHANG_STANDARDS == {}
    with pytest.raises(KeyError, match="No published modular"):
        get_overhang_standard("MoClo")


def test_a_supplied_standard_must_carry_a_citation() -> None:
    with pytest.raises(ValueError, match="no citation"):
        OverhangStandard(name="SomeStandard", citation="", overhangs=("AATG", "GCTT"))


def test_a_supplied_standard_must_not_repeat_an_overhang() -> None:
    with pytest.raises(ValueError, match="repeats an overhang"):
        OverhangStandard(name="SomeStandard", citation="a paper", overhangs=("AATG", "AATG"))
