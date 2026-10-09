from __future__ import annotations

import json
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Iterable

from Bio import SeqIO
from Bio.Align import PairwiseAligner
from Bio.SeqFeature import SeqFeature
from Bio.SeqRecord import SeqRecord

from packages.core.schemas import AnnotatedFeature, AnnotatedSequence
from packages.data_pipeline.marker_terms import contains_marker_term
from packages.data_pipeline.parse.classify import classify, is_annotation_complete
from packages.data_pipeline.parse.text_signals import contains_signal


REFERENCE_PATH = Path(__file__).resolve().parent / "references" / "component_library.json"
RESTRICTION_SITES = {
    "GAATTC",
    "AAGCTT",
    "GGATCC",
    "CTGCAG",
    "GTCGAC",
    "TCTAGA",
    "CCCGGG",
    "GGTACC",
    "GAGCTC",
    "GCATGC",
    "CCGCGG",
}
DNA_BASES = set("ACGTRYSWKMBDHVN")
REVERSE_COMPLEMENT_TABLE = str.maketrans("ACGTRYSWKMBDHVN", "TGCAYRSWMKVHDBN")
HIGH_IMPACT_OTHER_SIGNALS = (
    "5' LTR",
    "3' LTR",
    "5 prime LTR",
    "3 prime LTR",
    "long terminal repeat",
    "LTR",
    "WPRE",
    "woodchuck hepatitis virus posttranscriptional regulatory element",
    "psi packaging signal",
    "packaging signal",
    "RRE",
    "rev response element",
    "cPPT",
    "central polypurine tract",
    "IRES",
    "internal ribosome entry site",
    "P2A",
    "T2A",
    "E2A",
    "F2A",
    "2A peptide",
    "self-cleaving peptide",
    "sgRNA",
    "guide RNA",
    "gRNA",
    "tracrRNA",
    "crRNA",
    "shRNA",
    "ribosome binding site",
    "RBS",
    "Shine-Dalgarno",
    "operator",
    "lacO",
    "tetO",
    "enhancer",
)
HIGH_IMPACT_OTHER_FEATURE_TYPES = {
    "enhancer",
    "misc_feature",
    "misc_recomb",
    "misc_rna",
    "ncrna",
    "primer_bind",
    "regulatory",
    "repeat_region",
    "rna",
    "stem_loop",
}


@dataclass(frozen=True)
class ReferenceComponent:
    name: str
    type: str
    sequence: str
    aliases: tuple[str, ...] = ()
    replication_family: str | None = None
    replication_role: str | None = None
    host_class: str | None = None


@dataclass(frozen=True)
class ParserConfig:
    reference_identity_threshold: float = 0.85
    reference_coverage_threshold: float = 0.70
    trusted_annotation_confidence: float = 0.95
    reference_match_confidence: float = 0.82
    motif_confidence: float = 0.55


def parse_genbank_text(raw_text: str, config: ParserConfig | None = None) -> AnnotatedSequence:
    record = SeqIO.read(StringIO(raw_text), "genbank")
    return parse_seqrecord(record, config=config)


def parse_seqrecord(record: SeqRecord, config: ParserConfig | None = None) -> AnnotatedSequence:
    config = config or ParserConfig()
    sequence = str(record.seq).upper()
    topology = "circular" if record.annotations.get("topology") == "circular" else "linear"
    metadata_text = trusted_metadata_text(record)
    features: list[AnnotatedFeature] = []

    features.extend(features_from_annotations(record, config))
    references = load_reference_components()
    features.extend(features_from_reference_matches(sequence, features, references, config))
    features.extend(features_from_motifs(sequence, features, config))

    features = sorted(dedupe_features(features), key=lambda item: (item.start, item.end, item.type, item.name))
    provisional = AnnotatedSequence(
        sequence=sequence,
        topology=topology,
        features=features,
        annotation_complete=False,
    )
    classification = classify(provisional, metadata_text=metadata_text)
    return AnnotatedSequence(
        sequence=sequence,
        topology=topology,
        features=features,
        vector_profile=classification.profile,
        annotation_complete=is_annotation_complete(provisional, classification.profile, metadata_text=metadata_text),
    )


def features_from_annotations(record: SeqRecord, config: ParserConfig) -> list[AnnotatedFeature]:
    features: list[AnnotatedFeature] = []
    for source_feature in record.features:
        component_type = normalize_feature_type(source_feature)
        if component_type is None:
            continue
        start, end = feature_bounds(source_feature)
        if end <= start:
            continue
        features.append(
            AnnotatedFeature(
                type=component_type,
                start=start,
                end=end,
                strand=source_feature.location.strand or 0,
                name=best_feature_name(source_feature, fallback=component_type),
                confidence=config.trusted_annotation_confidence,
            )
        )
    return features


def normalize_feature_type(feature: SeqFeature) -> str | None:
    text = qualifier_text(feature).lower()
    feature_type = feature.type.lower()
    if feature_type == "rep_origin" or any(
        contains_signal(text, signal) for signal in ("origin of replication", "pmb1", "cole1")
    ):
        return "ORI"
    if feature_type == "promoter":
        return "promoter"
    if feature_type == "regulatory" and contains_signal(text, "promoter"):
        return "promoter"
    if feature_type in {"terminator", "polya_signal", "polya_site"}:
        return "terminator"
    if feature_type in {"regulatory", "misc_feature"} and any(
        contains_signal(text, signal) for signal in ("terminator", "polya", "polyadenylation")
    ):
        return "terminator"
    if feature_type in HIGH_IMPACT_OTHER_FEATURE_TYPES and any(
        contains_signal(text, signal) for signal in HIGH_IMPACT_OTHER_SIGNALS
    ):
        return "other"
    if feature_type == "misc_feature" and any(
        contains_signal(text, signal) for signal in ("multiple cloning", "polylinker", "mcs")
    ):
        return "MCS"
    if feature_type in {"cds", "gene", "misc_feature"} and contains_marker_term(text):
        return "marker"
    if feature_type == "cds":
        return "GOI"
    return None


def features_from_reference_matches(
    sequence: str,
    existing: list[AnnotatedFeature],
    references: list[ReferenceComponent],
    config: ParserConfig,
) -> list[AnnotatedFeature]:
    matches: list[AnnotatedFeature] = []
    for reference in references:
        if any(feature.type == reference.type and names_match(feature.name, reference.name, reference.aliases) for feature in existing):
            continue
        match = find_reference_match(sequence, reference, config)
        if match is None:
            continue
        start, end, strand, identity, coverage = match
        if overlaps_existing(start, end, existing + matches, reference.type):
            continue
        confidence = min(0.90, config.reference_match_confidence + 0.05 * max(identity - config.reference_identity_threshold, 0))
        matches.append(
            AnnotatedFeature(
                type=reference.type,
                start=start,
                end=end,
                strand=strand,
                name=reference.name,
                confidence=confidence,
            )
        )
    return matches


def find_reference_match(
    sequence: str,
    reference: ReferenceComponent,
    config: ParserConfig,
) -> tuple[int, int, int, float, float] | None:
    ref = reference.sequence.upper()
    direct = sequence.find(ref)
    if direct >= 0:
        return direct, direct + len(ref), 1, 1.0, 1.0
    reverse_ref = reverse_complement(ref)
    reverse_direct = sequence.find(reverse_ref)
    if reverse_direct >= 0:
        return reverse_direct, reverse_direct + len(reverse_ref), -1, 1.0, 1.0

    best_match: tuple[int, int, int, float, float] | None = None
    for candidate in seeded_reference_alignments(sequence, ref, 1, config):
        if best_match is None or candidate[3] * candidate[4] > best_match[3] * best_match[4]:
            best_match = candidate
    for candidate in seeded_reference_alignments(sequence, reverse_ref, -1, config):
        if best_match is None or candidate[3] * candidate[4] > best_match[3] * best_match[4]:
            best_match = candidate
    return best_match


def seeded_reference_alignments(
    sequence: str,
    ref: str,
    strand: int,
    config: ParserConfig,
    *,
    max_windows: int = 20,
    padding: int = 80,
) -> list[tuple[int, int, int, float, float]]:
    windows = candidate_windows(sequence, ref, max_windows=max_windows, padding=padding)
    matches: list[tuple[int, int, int, float, float]] = []
    for window_start, window_end in windows:
        window = sequence[window_start:window_end]
        match = align_reference_window(window, ref, strand, config)
        if match is None:
            continue
        start, end, match_strand, identity, coverage = match
        matches.append((window_start + start, window_start + end, match_strand, identity, coverage))
    return matches


def candidate_windows(
    sequence: str,
    ref: str,
    *,
    max_windows: int,
    padding: int,
) -> list[tuple[int, int]]:
    if len(ref) < 24:
        return []
    seed_length = min(24, max(12, len(ref) // 4))
    seed_starts = list(range(0, max(1, len(ref) - seed_length + 1), seed_length))
    final_seed_start = len(ref) - seed_length
    if final_seed_start not in seed_starts:
        seed_starts.append(final_seed_start)

    windows: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for seed_start in seed_starts:
        seed = ref[seed_start : seed_start + seed_length]
        if len(seed) < seed_length or set(seed) - DNA_BASES:
            continue
        offset = sequence.find(seed)
        while offset >= 0 and len(windows) < max_windows:
            start = max(0, offset - seed_start - padding)
            end = min(len(sequence), offset - seed_start + len(ref) + padding)
            window = (start, end)
            if window not in seen:
                seen.add(window)
                windows.append(window)
            offset = sequence.find(seed, offset + 1)
        if len(windows) >= max_windows:
            break
    return windows


def align_reference_window(
    sequence: str,
    ref: str,
    strand: int,
    config: ParserConfig,
) -> tuple[int, int, int, float, float] | None:
    aligner = PairwiseAligner(mode="local")
    aligner.match_score = 2
    aligner.mismatch_score = -1
    aligner.open_gap_score = -5
    aligner.extend_gap_score = -1
    try:
        alignment = aligner.align(sequence, ref)[0]
    except IndexError:
        return None
    target_blocks, query_blocks = alignment.aligned
    ref_aligned_bases = sum(query_end - query_start for query_start, query_end in query_blocks)
    if ref_aligned_bases == 0:
        return None
    identities = 0
    for (target_start, target_end), (query_start, query_end) in zip(target_blocks, query_blocks):
        target_segment = sequence[target_start:target_end]
        query_segment = ref[query_start:query_end]
        identities += sum(1 for seq_base, ref_base in zip(target_segment, query_segment) if seq_base == ref_base)
    identity = identities / ref_aligned_bases
    coverage = ref_aligned_bases / len(ref)
    if identity < config.reference_identity_threshold or coverage < config.reference_coverage_threshold:
        return None
    start = min(int(block[0]) for block in target_blocks)
    end = max(int(block[1]) for block in target_blocks)
    return int(start), int(end), strand, identity, coverage


def reverse_complement(sequence: str) -> str:
    return sequence.translate(REVERSE_COMPLEMENT_TABLE)[::-1]


def features_from_motifs(
    sequence: str,
    existing: list[AnnotatedFeature],
    config: ParserConfig,
    *,
    window_size: int = 90,
    min_sites: int = 5,
) -> list[AnnotatedFeature]:
    best: tuple[int, int, set[str]] | None = None
    for start in range(0, max(1, len(sequence) - window_size + 1), 10):
        window = sequence[start : start + window_size]
        sites = {site for site in RESTRICTION_SITES if site in window}
        if len(sites) >= min_sites and (best is None or len(sites) > len(best[2])):
            first = min(window.index(site) for site in sites)
            last = max(window.index(site) + len(site) for site in sites)
            best = (start + first, start + last, sites)
    if best is None:
        return []
    start, end, sites = best
    if overlaps_existing(start, end, existing, "MCS"):
        return []
    return [
        AnnotatedFeature(
            type="MCS",
            start=start,
            end=end,
            strand=0,
            name=f"restriction-site dense MCS candidate ({len(sites)} sites)",
            confidence=config.motif_confidence,
        )
    ]


def load_reference_components(path: Path = REFERENCE_PATH) -> list[ReferenceComponent]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    components = []
    for item in payload["components"]:
        components.append(
            ReferenceComponent(
                name=item["name"],
                type=item["type"],
                sequence="".join(item["sequence"].upper().split()),
                aliases=tuple(item.get("aliases", [])),
                replication_family=item.get("replication_family"),
                replication_role=item.get("replication_role"),
                host_class=item.get("host_class"),
            )
        )
    return components


def trusted_metadata_text(record: SeqRecord) -> str:
    fields: list[str] = [record.id, record.name, record.description]
    for key in ("source", "organism"):
        value = record.annotations.get(key)
        if value:
            fields.append(str(value))
    for keyword in record.annotations.get("keywords", []):
        fields.append(str(keyword))
    return " ".join(field for field in fields if field)


def dedupe_features(features: Iterable[AnnotatedFeature]) -> list[AnnotatedFeature]:
    result: list[AnnotatedFeature] = []
    for feature in sorted(features, key=lambda item: item.confidence, reverse=True):
        if overlaps_existing(feature.start, feature.end, result, str(feature.type)):
            continue
        result.append(feature)
    return result


def overlaps_existing(start: int, end: int, features: list[AnnotatedFeature], feature_type: str) -> bool:
    for feature in features:
        if str(feature.type) != feature_type:
            continue
        overlap = max(0, min(end, feature.end) - max(start, feature.start))
        shorter = max(1, min(end - start, feature.end - feature.start))
        if overlap / shorter >= 0.50:
            return True
    return False


def names_match(name: str, reference_name: str, aliases: tuple[str, ...]) -> bool:
    normalized = name.strip().lower()
    return normalized == reference_name.lower() or normalized in {alias.lower() for alias in aliases}


def feature_bounds(feature: SeqFeature) -> tuple[int, int]:
    parts = getattr(feature.location, "parts", None)
    if parts:
        starts = [int(part.start) for part in parts]
        ends = [int(part.end) for part in parts]
        return min(starts), max(ends)
    return int(feature.location.start), int(feature.location.end)


def best_feature_name(feature: SeqFeature, *, fallback: str) -> str:
    for key in ("label", "standard_name", "gene", "product", "note", "regulatory_class", "bound_moiety"):
        values = feature.qualifiers.get(key)
        if values and values[0]:
            return str(values[0])
    return fallback


def qualifier_text(feature: SeqFeature) -> str:
    values: list[str] = [feature.type]
    for key, raw_values in feature.qualifiers.items():
        values.append(str(key))
        values.extend(str(value) for value in raw_values)
    return " ".join(values)
