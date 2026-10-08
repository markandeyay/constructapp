from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb

from packages.core.schemas import AnnotatedSequence, SequenceSpan


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class DesignRecord:
    design_id: str
    session_id: str
    job_id: str
    annotated_sequence: AnnotatedSequence
    created_at: datetime
    updated_at: datetime

    #: Templates the generator was grounded in, and the per span attribution of
    #: the stored bases. Both default to empty because a provenance claim that is
    #: absent must not be confused with one that is broad: an empty list says the
    #: store was told nothing, not that the design came from nowhere in
    #: particular. Defaults also keep every existing construction compiling.
    template_ids: list[str] = field(default_factory=list)
    sequence_spans: list[SequenceSpan] = field(default_factory=list)


class DesignStore(Protocol):
    def create(
        self,
        *,
        session_id: str,
        job_id: str,
        annotated_sequence: AnnotatedSequence,
        design_id: str | None = None,
        template_ids: list[str] | None = None,
        sequence_spans: list[SequenceSpan] | None = None,
    ) -> DesignRecord: ...

    def get(self, design_id: str) -> DesignRecord | None: ...


@dataclass
class InMemoryDesignStore:
    records: dict[str, DesignRecord] = field(default_factory=dict)

    def create(
        self,
        *,
        session_id: str,
        job_id: str,
        annotated_sequence: AnnotatedSequence,
        design_id: str | None = None,
        template_ids: list[str] | None = None,
        sequence_spans: list[SequenceSpan] | None = None,
    ) -> DesignRecord:
        now = utc_now()
        record = DesignRecord(
            design_id=design_id or f"design_{uuid4().hex}",
            session_id=session_id,
            job_id=job_id,
            annotated_sequence=annotated_sequence,
            created_at=now,
            updated_at=now,
            # Copied rather than aliased: the caller's lists stay the caller's, so
            # a later mutation there cannot quietly rewrite a stored provenance
            # claim that a reader has already acted on.
            template_ids=list(template_ids or []),
            sequence_spans=list(sequence_spans or []),
        )
        self.records[record.design_id] = record
        return record

    def get(self, design_id: str) -> DesignRecord | None:
        return self.records.get(design_id)


@dataclass(frozen=True)
class PostgresDesignStore:
    database_url: str

    def create(
        self,
        *,
        session_id: str,
        job_id: str,
        annotated_sequence: AnnotatedSequence,
        design_id: str | None = None,
        template_ids: list[str] | None = None,
        sequence_spans: list[SequenceSpan] | None = None,
    ) -> DesignRecord:
        now = utc_now()
        record = DesignRecord(
            design_id=design_id or f"design_{uuid4().hex}",
            session_id=session_id,
            job_id=job_id,
            annotated_sequence=annotated_sequence,
            created_at=now,
            updated_at=now,
            template_ids=list(template_ids or []),
            sequence_spans=list(sequence_spans or []),
        )
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """
                INSERT INTO designs (id, session_id, job_id, status, payload, result, created_at, updated_at)
                VALUES (%s, %s, %s, 'ready', %s, %s, %s, %s)
                """,
                (
                    record.design_id,
                    record.session_id,
                    record.job_id,
                    # The payload column was written as an empty object and read
                    # by nobody, so the provenance fields go there instead of
                    # requiring a migration. They live beside each other because
                    # they answer one question together: which records back this
                    # design, and which bases each of them backs.
                    Jsonb(
                        {
                            "template_ids": record.template_ids,
                            "sequence_spans": [span.model_dump(mode="json") for span in record.sequence_spans],
                        }
                    ),
                    Jsonb({"annotated_sequence": record.annotated_sequence.model_dump(mode="json")}),
                    record.created_at,
                    record.updated_at,
                ),
            )
        return record

    def get(self, design_id: str) -> DesignRecord | None:
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute(
                """
                SELECT id, session_id, job_id, result->'annotated_sequence', payload, created_at, updated_at
                FROM designs
                WHERE id = %s
                """,
                (design_id,),
            ).fetchone()
        if row is None:
            return None
        # Rows written before provenance was stored hold `{}` or NULL here, and
        # they must still load: a design that predates the field is unattributed,
        # which the empty lists say honestly, and failing the read instead would
        # make old designs unopenable to no one's benefit.
        payload = row[4] if isinstance(row[4], dict) else {}
        return DesignRecord(
            design_id=row[0],
            session_id=row[1],
            job_id=row[2],
            annotated_sequence=AnnotatedSequence.model_validate(row[3]),
            created_at=row[5],
            updated_at=row[6],
            template_ids=[str(item) for item in payload.get("template_ids") or []],
            # Validated on read rather than trusted, so a span that lost its
            # length invariant in storage is caught here and not downstream.
            sequence_spans=[SequenceSpan.model_validate(item) for item in payload.get("sequence_spans") or []],
        )
