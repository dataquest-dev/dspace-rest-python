"""DSpace 7 REST API client."""

from typing import TYPE_CHECKING, Any

from .models import (
    HALResource,
    AddressableHALResource,
    ExternalDataObject,
    DSpaceObject,
    SimpleDSpaceObject,
    Item,
    Community,
    Collection,
    Bundle,
    Bitstream,
    Group,
    User,
    InProgressSubmission,
    WorkspaceItem,
    EntityType,
    RelationshipType,
    License,
    Label,
    ResourcePolicy,
)

if TYPE_CHECKING:
    from .client import DSpaceClient

__all__ = [
    "DSpaceClient",
    "HALResource",
    "AddressableHALResource",
    "ExternalDataObject",
    "DSpaceObject",
    "SimpleDSpaceObject",
    "Item",
    "Community",
    "Collection",
    "Bundle",
    "Bitstream",
    "Group",
    "User",
    "InProgressSubmission",
    "WorkspaceItem",
    "EntityType",
    "RelationshipType",
    "License",
    "Label",
    "ResourcePolicy",
]


def __getattr__(name: str) -> Any:
    # client reads its env-based class defaults (DSPACE_API_ENDPOINT, PROXY_URL,
    # ...) at import time, so it is imported on first use, never as a side
    # effect of importing the package or one of its submodules
    if name == "DSpaceClient":
        from .client import DSpaceClient  # pylint: disable=import-outside-toplevel
        return DSpaceClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
