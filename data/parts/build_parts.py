"""Rebuild or verify the AAV part registry from NCBI GenBank.

Every part record in data/parts/ is a verbatim slice of a GenBank flat file,
cut at the coordinates of an annotated feature. This script is the executable
form of that statement: it fetches each source record, locates the annotated
feature, checks that the feature type and note match what was expected, slices
the sequence, and either writes the JSON record or compares it with the file
already on disk.

Usage (run from the repository root):

    python data/parts/build_parts.py --write    # fetch and (re)write every record
    python data/parts/build_parts.py --verify   # fetch and compare, exit 1 on any difference

Network access to eutils.ncbi.nlm.nih.gov is required. No API key is used, so
requests are throttled to stay under the 3 requests per second default limit
documented in the NCBI E-utilities help. The query carries tool=construct-build
and no email parameter.

Nothing here is a biological constant. Coordinates are 1-based inclusive, as in
the GenBank FEATURES table.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path

EUTILS_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
TOOL_NAME = "construct-build"

# Minimum spacing between requests. NCBI documents 3 requests per second without
# an API key; 0.4 s keeps the rate at 2.5 per second.
MIN_REQUEST_INTERVAL_S = 0.4

PARTS_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class PartSpec:
    category: str
    stem: str
    name: str
    accession: str
    start: int
    end: int
    feature_type: str
    note_pattern: str | None
    host_compatibility: tuple[str, ...]
    tissue_specificity: str | None
    notes: str
    citation: str
    literature: str | None = None


MAMMAL = ("mammalian_general",)

PARTS: tuple[PartSpec, ...] = (
    PartSpec(
        "itr", "aav2_itr_left", "AAV2 inverted terminal repeat, left (5' ITR)",
        "NC_001401.2", 1, 145, "repeat_region", r"inverted terminal repeat", MAMMAL, None,
        "Left ITR as it appears on the reference genome plus strand. Contains the A, B, C and D "
        "regions (145 nt; the larger figure in Appendix B includes the D sequence). The reference "
        "record also annotates a flip oriented DNA feature at 42..83.",
        "RefSeq NC_001401.2",
        "doi:10.1128/JVI.45.2.555-564.1983",
    ),
    PartSpec(
        "itr", "aav2_itr_right", "AAV2 inverted terminal repeat, right (3' ITR)",
        "NC_001401.2", 4535, 4679, "repeat_region", r"inverted terminal repeat", MAMMAL, None,
        "Right ITR as it appears on the reference genome plus strand. Its reverse complement "
        "matches the left ITR at 128 of 145 positions (88.3 percent) because the left ITR carries "
        "the flip orientation of the B and C arms and the right ITR the flop orientation, so each "
        "ITR must be compared with its own reference record, not with the other one. Placing it 3' "
        "of the cassette in this orientation gives the inverted arrangement that check "
        "aav.itr_orientation tests for. The reference record annotates a flop oriented DNA "
        "feature at 4597..4638.",
        "RefSeq NC_001401.2",
        "doi:10.1128/JVI.45.2.555-564.1983",
    ),
    PartSpec(
        "promoter", "cmv", "CMV immediate early enhancer and promoter",
        "AF396260.1", 150, 812, "regulatory", r"^CMV$", MAMMAL, "ubiquitous",
        "Strong, ubiquitous expression. Can silence over time in some tissues (Appendix B). The "
        "annotated feature is longer than the roughly 584 bp enhancer plus promoter core because "
        "it runs on through the transcription start and 5' untranslated region of the CMV "
        "immediate early gene.",
        "GenBank AF396260.1",
    ),
    PartSpec(
        "promoter", "cag", "CAG promoter (CMV enhancer, chicken beta-actin promoter and intron)",
        "ON785708.1", 221, 1859, "regulatory", None, MAMMAL, "ubiquitous",
        "Strong, ubiquitous expression. Large, so often the first element cut when over budget "
        "(Appendix B). The source feature is an unnamed promoter annotation; its identity as the "
        "CMV enhancer plus chicken beta-actin promoter plus intron architecture was established "
        "by alignment to independently annotated records, see PROVENANCE.md.",
        "GenBank ON785708.1",
        "doi:10.1016/0378-1119(91)90434-d",
    ),
    PartSpec(
        "promoter", "ef1a", "EF-1 alpha promoter, full length",
        "MT586119.1", 593, 1776, "regulatory", r"EF-1alpha", MAMMAL, "ubiquitous",
        "Ubiquitous, durable expression (Appendix B). Contains the EFS core promoter sequence "
        "within it.",
        "GenBank MT586119.1",
        "doi:10.1016/0378-1119(90)90091-5",
    ),
    PartSpec(
        "promoter", "efs", "EFS, short EF-1 alpha core promoter",
        "MT891328.1", 529, 740, "regulatory", r"EF-1alpha core promoter", MAMMAL, "ubiquitous",
        "The compact ubiquitous option. Weaker than CAG. Valuable when capacity is tight "
        "(Appendix B). Annotated in the source record as the EF-1alpha core promoter.",
        "GenBank MT891328.1",
    ),
    PartSpec(
        "promoter", "hsyn1", "Human synapsin I promoter (hSyn1)",
        "MH282432.1", 216, 687, "regulatory", r"hSyn promoter", MAMMAL, "cns_neuron",
        "Neuron-specific (Appendix B). The source annotation cites a 2003 Gene Therapy paper for neuron "
        "specific expression.",
        "GenBank MH282432.1",
        "doi:10.1038/sj.gt.3301905",
    ),
    PartSpec(
        "promoter", "cbh", "CBh promoter (hybrid CMV enhancer and chicken beta-actin)",
        "KU341333.1", 442, 1240, "regulatory", r"CBh promoter", MAMMAL, "ubiquitous",
        "Hybrid, ubiquitous (Appendix B). The CBh promoter is described in a 2011 Human Gene Therapy "
        "paper as a hybrid form of the chicken beta-actin promoter of roughly 800 bp.",
        "GenBank KU341333.1",
        "doi:10.1089/hum.2010.245",
    ),
    PartSpec(
        "promoter", "gfap", "GfaABC1D astrocyte promoter",
        "PZ285974.1", 1214, 1904, "regulatory", r"gfaABC1D promoter", MAMMAL, "cns_astrocyte",
        "Astrocyte-specific (Appendix B lists GFAP at roughly 680 bp). Annotated gfaABC1D "
        "promoter in the source record.",
        "GenBank PZ285974.1",
        "doi:10.1002/glia.20622",
    ),
    PartSpec(
        "promoter", "mecp2_mini", "MeCP2 mini promoter (meP229)",
        "PY026695.1", 1, 225, "misc_feature", r"meP229 Promoter", MAMMAL, "cns_neuron",
        "Compact, neuronal (Appendix B). Lowest-confidence source in the registry: a patent "
        "sequence record (US 12359219 B2) rather than a vector deposit, annotated "
        "meP229 although the record is 225 bp long. It matches the 3' end of the patent's meP426 "
        "record (PY026693.1) exactly, see PROVENANCE.md.",
        "GenBank PY026695.1 (patent US 12359219 B2)",
    ),
    PartSpec(
        "polya", "bgh", "Bovine growth hormone polyadenylation signal",
        "ON785708.1", 3786, 4010, "regulatory", r"bovine growth hormone polyadenylation signal",
        MAMMAL, None,
        "Common default polyadenylation signal (Appendix B).",
        "GenBank ON785708.1",
    ),
    PartSpec(
        "polya", "sv40", "SV40 polyadenylation signal",
        "KX449554.1", 4852, 4986, "regulatory", r"SV40 polyadenylation signal", MAMMAL, None,
        "Smaller alternative to bGH (Appendix B).",
        "GenBank KX449554.1",
    ),
    PartSpec(
        "enhancer", "wpre", "Woodchuck hepatitis virus posttranscriptional regulatory element",
        "MH282432.1", 2868, 3456, "regulatory", r"^WPRE$", MAMMAL, None,
        "Boosts expression. Optional, and the obvious cut when over budget (Appendix B).",
        "GenBank MH282432.1",
        "doi:10.1128/JVI.73.4.2886-2892.1999",
    ),
    PartSpec(
        "intron", "chimeric", "Chimeric intron (human beta-globin donor, immunoglobulin acceptor)",
        "KT345943.1", 17, 157, "intron", r"beta-globin-IgG-chimeric intron", MAMMAL, None,
        "Optional (Appendix B). Annotated beta-globin-IgG-chimeric intron in the source record.",
        "GenBank KT345943.1",
    ),
)


_last_request = [0.0]


def efetch_genbank(accession: str) -> str:
    wait = MIN_REQUEST_INTERVAL_S - (time.time() - _last_request[0])
    if wait > 0:
        time.sleep(wait)
    query = urllib.parse.urlencode(
        {"db": "nuccore", "id": accession, "rettype": "gb", "retmode": "text", "tool": TOOL_NAME}
    )
    last_error: Exception | None = None
    for _ in range(4):
        try:
            with urllib.request.urlopen(f"{EUTILS_EFETCH}?{query}", timeout=60) as response:
                _last_request[0] = time.time()
                return response.read().decode("utf-8")
        except Exception as exc:  # network failures are retried, then raised loudly
            last_error = exc
            time.sleep(2.0)
    raise RuntimeError(f"could not fetch {accession}: {last_error}")


def parse_record(text: str) -> tuple[str, str, str, list[tuple[str, int, int, str]]]:
    """Return (accession.version, definition, sequence, features) from a GenBank flat file.

    Each feature is (type, start, end, qualifier_text) with 1-based inclusive
    coordinates taken from the outer bounds of the location string.
    """
    version = re.search(r"^VERSION\s+(\S+)", text, re.M).group(1)
    definition_match = re.search(r"^DEFINITION\s+(.*?)\n(?=[A-Z])", text, re.M | re.S)
    definition = " ".join(definition_match.group(1).split())
    origin = text.split("\nORIGIN", 1)[1].split("\n//", 1)[0]
    sequence = "".join(ch for ch in origin if ch.isalpha()).upper()
    table = text.split("\nFEATURES", 1)[1].split("\nORIGIN", 1)[0].split("\n", 1)[1]
    blocks: list[list[str]] = []
    for line in table.split("\n"):
        if re.match(r"^ {5}\S", line):
            blocks.append([line])
        elif blocks:
            blocks[-1].append(line)
    features: list[tuple[str, int, int, str]] = []
    for block in blocks:
        head = block[0]
        ftype = head[5:21].strip()
        numbers = [int(n) for n in re.findall(r"\d+", head[21:])]
        if not numbers:
            continue
        qualifiers = " ".join(part.strip() for part in block[1:])
        features.append((ftype, min(numbers), max(numbers), qualifiers))
    return version, definition, sequence, features


def _scrub_names(text: str) -> str:
    """Replace parenthetical author-year citations inside a GenBank note.

    The repository carries no personal names. The citation itself is preserved
    through the DOI recorded in each part's notes.
    """
    return re.sub(r"\s*\([A-Z][A-Za-z-]+ et al\.?,? \d{4}\)", " (author citation omitted)", text)


def build_record(spec: PartSpec, retrieved_on: str) -> dict:
    text = efetch_genbank(spec.accession)
    version, definition, sequence, features = parse_record(text)
    if version != spec.accession:
        raise RuntimeError(f"{spec.accession}: NCBI returned version {version}")
    matches = [f for f in features if f[0] == spec.feature_type and f[1] == spec.start and f[2] == spec.end]
    if not matches:
        raise RuntimeError(f"{spec.accession}: no {spec.feature_type} feature at {spec.start}..{spec.end}")
    ftype, _, _, qualifiers = matches[0]
    note_values = re.findall(r'/note="([^"]*)"', qualifiers)
    if spec.note_pattern is not None:
        if not any(re.search(spec.note_pattern, value, re.I) for value in note_values):
            raise RuntimeError(
                f"{spec.accession} {spec.start}..{spec.end}: note {note_values!r} does not match {spec.note_pattern!r}"
            )
    part_sequence = sequence[spec.start - 1 : spec.end]
    if len(part_sequence) != spec.end - spec.start + 1:
        raise RuntimeError(f"{spec.accession}: coordinates run past the end of the record")
    if set(part_sequence) - set("ACGT"):
        raise RuntimeError(f"{spec.accession} {spec.start}..{spec.end}: non-ACGT bases present")
    reg_class = re.search(r'/regulatory_class="([^"]*)"', qualifiers)
    source = (
        f"GenBank {spec.accession}, {spec.feature_type}"
        f"{' (' + reg_class.group(1) + ')' if reg_class else ''} feature {spec.start}..{spec.end}"
    )
    atg_count = len(re.findall("(?=ATG)", part_sequence))
    notes = spec.notes + f" The sense strand contains {atg_count} ATG trinucleotide(s)."
    if spec.literature:
        notes += (
            f" Literature describing the element: {spec.literature} "
            "(the sequence itself comes from the GenBank record, not from the paper)."
        )
    return {
        "id": f"{spec.category}.{spec.stem}",
        "name": spec.name,
        "category": spec.category,
        "length_bp": len(part_sequence),
        "sequence": part_sequence,
        "host_compatibility": list(spec.host_compatibility),
        "tissue_specificity": spec.tissue_specificity,
        "source": source,
        "notes": notes,
        "citation": spec.citation,
        "provenance": {
            "accession": spec.accession,
            "record_title": definition,
            "feature_type": ftype,
            "feature_note": _scrub_names(" ".join(note_values)) or None,
            "coordinates": [spec.start, spec.end],
            "strand": 1,
            "retrieved_on": retrieved_on,
            "retrieved_via": f"NCBI E-utilities efetch, db=nuccore, rettype=gb, tool={TOOL_NAME}",
        },
    }


def render(record: dict) -> str:
    return json.dumps(record, indent=2, ensure_ascii=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="fetch and write every record")
    mode.add_argument("--verify", action="store_true", help="fetch and compare against the files on disk")
    args = parser.parse_args()

    today = date.today().isoformat()
    failures = 0
    for spec in PARTS:
        path = PARTS_DIR / spec.category / f"{spec.stem}.json"
        record = build_record(spec, today)
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render(record), encoding="utf-8", newline="\n")
            print(f"wrote  {record['id']:<22} {record['length_bp']:>5} bp  {spec.accession} {spec.start}..{spec.end}")
        else:
            on_disk = json.loads(path.read_text(encoding="utf-8"))
            same = on_disk["sequence"] == record["sequence"] and on_disk["length_bp"] == record["length_bp"]
            print(f"{'ok    ' if same else 'DIFFER'} {record['id']}")
            failures += 0 if same else 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
