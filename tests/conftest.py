"""Suite wide fixtures.

Currently one concern: keeping the section 11.1 export audit log out of the
repository when tests exercise a capability route.
"""

from __future__ import annotations

import pytest

from packages.application.screening.audit import AUDIT_LOG_PATH_ENV


@pytest.fixture(autouse=True)
def export_audit_path(tmp_path, monkeypatch):
    """Redirect the export audit log into a per test temporary file.

    Autouse and suite wide rather than per module, for two reasons.

    Every request to an AAV, assembly or guide RNA design endpoint is a screened
    export and appends an audit entry. Without this fixture those tests append to
    the repository's own `data/audit/export_audit.jsonl`, which both dirties a
    real operational record and makes any test that counts entries depend on how
    many other tests happened to run first. Scoping it here rather than in each
    capability's test module also means a route test added later inherits the
    redirect instead of quietly reintroducing the problem.

    Function scoped rather than session scoped on purpose: a session scoped log
    would accumulate across tests, so a test asserting how many entries its own
    request wrote could only do so by reading the tail and assuming nothing
    interleaved. A fresh file per test makes those assertions exact.

    Returns the path, so a test that wants to read the entries it produced can
    request this fixture by name.
    """
    path = tmp_path / "export_audit.jsonl"
    monkeypatch.setenv(AUDIT_LOG_PATH_ENV, str(path))
    return path
