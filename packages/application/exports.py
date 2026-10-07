from __future__ import annotations

import json
from io import StringIO
from typing import Literal, cast

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from packages.core.schemas import AnnotatedFeature, AnnotatedSequence
from packages.data_pipeline.parse.sequence_parser import parse_seqrecord


ExportFormat = Literal["genbank", "fasta"]

SUPPORTED_EXPORT_FORMATS = frozenset({"genbank", "fasta"})
EXPORT_RECORD_ID = "annotated_sequence"
KEYWORD_PREFIX = "CONSTRUCT_EXPORT"
FASTA_METADATA_PREFIX = "construct_meta="

GENBANK_FEATURE_TYPES = {
    "ORI": "rep_origin",
    "promoter": "promoter",
    "GOI": "CDS",
    "marker": "CDS",
    "MCS": "misc_feature",
    "terminator": "terminator",
    "other": "misc_feature",
}


def validate_export_format(value: str) -> ExportFormat:
    normalized = value.strip().lower()
    if normalized not in SUPPORTED_EXPORT_FORMATS:
        expected = ", ".join(sorted(SUPPORTED_EXPORT_FORMATS))
        raise ValueError(f"unsupported export format {value!r}; expected one of: {expected}")
    return cast(ExportFormat, normalized)


def export_annotated_sequence(sequence: AnnotatedSequence, *, format: str) -> str:
    export_format = validate_export_format(format)
    if export_format == "genbank":
        return _export_genbank(sequence)
    return _export_fasta(sequence)


def read_annotated_sequence(payload: str, *, format: str) -> AnnotatedSequence:
    export_format = validate_export_format(format)
    if export_format == "genbank":
        return _read_genbank(payload)
    return _read_fasta(payload)


def _export_genbank(sequence: AnnotatedSequence) -> str:
    record = SeqRecord(
        Seq(sequence.sequence),
        id=EXPORT_RECORD_ID,
        name=EXPORT_RECORD_ID,
        description="Construct annotated sequence export",
    )
    record.annotations["molecule_type"] = "DNA"
    record.annotations["topology"] = str(sequence.topology)
    record.annotations["keywords"] = _record_keywords(sequence)
    record.features = [_feature_to_seqfeature(feature) for feature in sequence.features]

    handle = StringIO()
    SeqIO.write(record, handle, "genbank")
    return handle.getvalue()


def _export_fasta(sequence: AnnotatedSequence) -> str:
    metadata = json.dumps(_sequence_metadata(sequence), separators=(",", ":"))
    record = SeqRecord(
        Seq(sequence.sequence),
        id=EXPORT_RECORD_ID,
        name=EXPORT_RECORD_ID,
        description=f"{FASTA_METADATA_PREFIX}{metadata}",
    )
    handle = StringIO()
    SeqIO.write(record, handle, "fasta")
    return handle.getvalue()


def _read_genbank(payload: str) -> AnnotatedSequence:
    record = SeqIO.read(StringIO(payload), "genbank")
    metadata = _record_metadata(record)
    if metadata is None:
        return parse_seqrecord(record)

    features = [_seqfeature_to_feature(feature) for feature in record.features if "construct_type" in feature.qualifiers]
    return AnnotatedSequence(
        sequence=str(record.seq).upper(),
        topology=metadata["topology"],
        features=features,
        vector_profile=metadata["vector_profile"],
        annotation_complete=metadata["annotation_complete"],
    )


def _read_fasta(payload: str) -> AnnotatedSequence:
    record = SeqIO.read(StringIO(payload), "fasta")
    metadata = _fasta_metadata(record.description)
    return AnnotatedSequence(
        sequence=str(record.seq).upper(),
        topology=metadata["topology"],
        features=[],
        vector_profile=metadata["vector_profile"],
        annotation_complete=metadata["annotation_complete"],
    )


def _feature_to_seqfeature(feature: AnnotatedFeature) -> SeqFeature:
    strand = None if feature.strand == 0 else feature.strand
    return SeqFeature(
        FeatureLocation(feature.start, feature.end, strand=strand),
        type=GENBANK_FEATURE_TYPES[str(feature.type)],
        qualifiers={
            "label": [feature.name],
            "note": [feature.name],
            "construct_type": [str(feature.type)],
            "construct_name": [feature.name],
            "construct_confidence": [f"{feature.confidence:.6f}"],
            "construct_strand": [str(feature.strand)],
        },
    )


def _seqfeature_to_feature(feature: SeqFeature) -> AnnotatedFeature:
    qualifiers = feature.qualifiers
    name = _qualifier_value(qualifiers, "construct_name") or _qualifier_value(qualifiers, "label") or str(feature.type)
    return AnnotatedFeature(
        type=_qualifier_value(qualifiers, "construct_type"),
        start=int(feature.location.start),
        end=int(feature.location.end),
        strand=int(_qualifier_value(qualifiers, "construct_strand", default=str(feature.location.strand or 0))),
        name=name,
        confidence=float(_qualifier_value(qualifiers, "construct_confidence", default="0.0")),
    )


def _sequence_metadata(sequence: AnnotatedSequence) -> dict[str, object]:
    return {
        "topology": str(sequence.topology),
        "vector_profile": sequence.vector_profile,
        "annotation_complete": sequence.annotation_complete,
    }


def _record_metadata(record: SeqRecord) -> dict[str, object] | None:
    keywords = [str(keyword) for keyword in record.annotations.get("keywords", [])]
    if not keywords or keywords[0] != KEYWORD_PREFIX:
        return None
    payload: dict[str, object] = {}
    for keyword in keywords[1:]:
        if "=" not in keyword:
            continue
        key, value = keyword.split("=", maxsplit=1)
        payload[key] = value
    return _normalize_metadata(payload)


def _fasta_metadata(description: str) -> dict[str, object]:
    if FASTA_METADATA_PREFIX not in description:
        return _normalize_metadata({})
    encoded = description.split(FASTA_METADATA_PREFIX, maxsplit=1)[1].strip()
    return _normalize_metadata(json.loads(encoded))


def _normalize_metadata(payload: dict[str, object]) -> dict[str, object]:
    topology = str(payload.get("topology", "linear")).lower()
    if topology not in {"circular", "linear"}:
        raise ValueError(f"unsupported topology {topology!r} in exported sequence")
    return {
        "topology": topology,
        "vector_profile": str(payload.get("vector_profile", "unknown")),
        "annotation_complete": str(payload.get("annotation_complete", "false")).lower() == "true",
    }


def _record_keywords(sequence: AnnotatedSequence) -> list[str]:
    metadata = _sequence_metadata(sequence)
    return [
        KEYWORD_PREFIX,
        f"topology={metadata['topology']}",
        f"vector_profile={metadata['vector_profile']}",
        f"annotation_complete={str(metadata['annotation_complete']).lower()}",
    ]


def _qualifier_value(qualifiers: dict[str, list[str]], key: str, default: str | None = None) -> str:
    values = qualifiers.get(key)
    if values and values[0]:
        return str(values[0])
    if default is None:
        raise ValueError(f"missing required qualifier {key!r} in exported GenBank feature")
    return default
