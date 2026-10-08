"""Capability router include block.

Source: section 13.3 of the engine capability system design. WP-02 creates this
file with the same three reserved, delimited regions as the capability
registry. Each capability package adds its router reference only inside its own
region. A merge conflict inside a region means a package wrote outside its own,
which is a spec violation to be reported rather than resolved by hand.

A region entry is a single inline `RouterInclude(...)` expression whose
`router` is a dotted `package.module:attribute` path to a FastAPI `APIRouter`,
so a package needs no import line outside its region. The router is imported
only when `include_capability_routers` runs.

Wiring `include_capability_routers(app)` into `create_app` is a one-line change
to `services/api/app.py`, which WP-02 does not own. It is filed as a cross-WP
request in PROGRESS.md.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RouterInclude:
    capability: str  # CapabilityKind value, for example "aav"
    router: str  # "package.module:attribute" of an APIRouter
    prefix: str = ""  # optional extra path prefix passed to include_router


CAPABILITY_ROUTERS: tuple[RouterInclude, ...] = (
    # ==== WP-03: AAV. Only WP-03 writes here. ====
    RouterInclude("aav", "services.api.routes.aav:router", ""),
    # ==== /WP-03 ====
    # ==== WP-04: assembly. Only WP-04 writes here. ====
    # ==== /WP-04 ====
    # ==== WP-05: guide RNA. Only WP-05 writes here. ====
    # ==== /WP-05 ====
)


def load_router(include: RouterInclude) -> Any:
    """Import and return the APIRouter named by an include entry."""
    module_name, separator, attribute = include.router.partition(":")
    if not separator or not module_name or not attribute:
        raise ValueError(f"router reference {include.router!r} must have the form 'package.module:attribute'")
    return getattr(importlib.import_module(module_name), attribute)


def include_capability_routers(app: Any) -> list[str]:
    """Include every registered capability router on `app`; return the capabilities included."""
    included: list[str] = []
    for include in CAPABILITY_ROUTERS:
        app.include_router(load_router(include), prefix=include.prefix)
        included.append(include.capability)
    return included
