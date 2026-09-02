# This software is licenced under the BSD 3-Clause licence
# available at https://opensource.org/licenses/BSD-3-Clause
# and described in the LICENSE.txt file in the root of this project

"""
DSpace REST API client library models.
Intended to make interacting with DSpace in Python 3 easier, particularly
when creating, updating, retrieving and deleting DSpace Objects.

@author Kim Shepherd <kim@shepherd.nz>
"""
from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
import json
from typing import Any


__all__ = [
    'HALResource', 'AddressableHALResource', 'ExternalDataObject', 'DSpaceObject',
    'SimpleDSpaceObject', 'Item', 'Community', 'Collection', 'Bundle', 'Bitstream',
    'Group', 'User', 'InProgressSubmission', 'WorkspaceItem', 'EntityType',
    'RelationshipType', 'License', 'Label', 'ResourcePolicy',
]


def _fresh(default: Any) -> Any:
    """
    Return a per-instance copy of a declared default.

    Mutable defaults must never be shared between instances - that is exactly
    the class-attribute bug these constructors are structured to make impossible.
    """
    return deepcopy(default) if isinstance(default, (dict, list, set)) else default


def _shallow(value: Any) -> Any:
    """Shallow copy of a value taken from an API resource."""
    return value.copy()


class HALResource:
    """
    Base class to represent HAL+JSON API resources

    Attribute *types* are declared in the class body as bare annotations and the
    *values* are assigned per instance in __init__, mostly through the shared
    _init_fields() helper. Nothing is given a class-level value: that would be a
    single object shared by every instance, so a mutable one (links, embedded,
    metadata, checkSum, sections) leaks mutations between them.
    """
    type: str | None
    links: dict[str, Any]
    embedded: dict[str, Any]

    def __init__(self, api_resource: dict[str, Any] | None = None) -> None:
        """
        Default constructor
        @param api_resource: optional API resource (JSON) from a GET response or successful POST can populate instance
        """
        self._from_d: dict[str, Any] | None = api_resource
        self._init_fields(api_resource, type=None)
        # _links / _embedded are HAL envelope keys rather than plain fields, and
        # a resource that carries no _links still gets the self-href placeholder.
        if api_resource is None:
            self.links = {}
            self.embedded = {}
        else:
            self.links = (deepcopy(api_resource['_links']) if '_links' in api_resource
                          else {'self': {'href': None}})
            self.embedded = (deepcopy(api_resource['_embedded'])
                             if '_embedded' in api_resource else {})

    def _init_fields(self, api_resource: dict[str, Any] | None,
                     copy: Callable[[Any], Any] | None = None, /,
                     **defaults: Any) -> None:
        """
        Assign each named attribute from `api_resource`, falling back to its default.

        Replaces the `self.x = <default>` + `if 'x' in api_resource: ...` pair
        every model used to repeat per field: each field is now named once,
        beside its default.

        @param api_resource: resource to read from; None or {} means "all defaults"
        @param copy:         copier for values taken from the resource; positional-only,
                             so it can never collide with a field name
        @param defaults:     field name -> default value
        """
        resource = api_resource or {}
        for attr, default in defaults.items():
            if attr in resource:
                value = resource[attr]
                setattr(self, attr, copy(value) if copy is not None else value)
            else:
                setattr(self, attr, _fresh(default))


class AddressableHALResource(HALResource):
    id: Any

    def __init__(self, api_resource: dict[str, Any] | None = None) -> None:
        super().__init__(api_resource)
        self._init_fields(api_resource, id=None)

    def as_dict(self) -> dict[str, Any]:
        return {'id': self.id}


class ExternalDataObject(HALResource):
    """
    Generic External Data Object as configured in DSpace's external data providers framework
    """
    id: Any
    display: Any
    value: Any
    externalSource: Any
    metadata: dict[str, Any]

    def __init__(self, api_resource: dict[str, Any] | None = None) -> None:
        """
        Default constructor
        @param api_resource: optional API resource (JSON) from a GET response or successful POST can populate instance
        """
        super().__init__(api_resource)
        self._init_fields(api_resource, id=None, display=None, value=None,
                          externalSource=None)
        self._init_fields(api_resource, deepcopy, metadata={})

    def get_metadata_values(self, field: str) -> list:
        """
        Return metadata values as simple list of strings
        @param field: DSpace field, eg. dc.creator
        @return: list of strings
        """
        values = []
        if field in self.metadata:
            values = self.metadata[field]
        return values


class DSpaceObject(HALResource):
    """
    Base class to represent DSpaceObject API resources
    The variables here are present in an _embedded response and the ones required for POST / PUT / PATCH
    operations are included in the dict returned by asDict(). Implements toJSON() as well.
    This class can be used on its own but is generally expected to be extended by other types: Item, Bitstream, etc.
    """
    id: Any
    uuid: str | None
    name: str | None
    handle: str | None
    lastModified: Any
    parent: Any
    metadata: dict[str, Any]

    def __init__(
        self,
        api_resource: dict[str, Any] | None = None,
        dso: DSpaceObject | None = None,
    ) -> None:
        """
        Default constructor
        @param api_resource: optional API resource (JSON) from a GET response or successful POST can populate instance
        """
        super().__init__(api_resource)
        if dso is not None:
            # copying another DSO: its as_dict() becomes the resource, and its
            # HAL links come across directly (as_dict() does not carry _links)
            api_resource = dso.as_dict()
            self.links = deepcopy(dso.links)
        # lastModified and parent are local-only: as_dict() emits lastModified,
        # but no constructor has ever read either one back off an API resource.
        self.lastModified = None
        self.parent = None
        self._init_fields(api_resource, id=None, uuid=None, type=None, name=None,
                          handle=None)
        self._init_fields(api_resource, deepcopy, metadata={})

    @property
    def resourcePolicies(self) -> Any:
        return (self._from_d or {}).get('resourcePolicies')

    def add_metadata(
        self,
        field: str,
        value,
        language=None,
        authority=None,
        confidence: int = -1,
        place=None,
    ) -> DSpaceObject | None:
        """
        Add metadata to a DSO. This is performed on the local object only, it is not an API operation (see patch)
        This is useful when constructing new objects for ingest.
        When doing simple changes like "retrieve a DSO, add some metadata, update" then it is best to use a patch
        operation, not this clas method. See
        :param field:
        :param value:
        :param language:
        :param authority:
        :param confidence:
        :param place:
        :return:
        """
        if field is None or value is None:
            return None
        if field in self.metadata:
            values = self.metadata[field]
            # Ensure we don't accidentally duplicate place value. If this place already exists, the user
            # should use a patch operation or we should allow another way to re-order / re-calc place?
            # For now, we'll just set place to none if it matches an existing place
            for v in values:
                if v['place'] == place:
                    place = None
                    break
        else:
            values = []
        values.append({"value": value, "language": language,
                       "authority": authority, "confidence": confidence, "place": place})
        self.metadata[field] = values

        # Return this as an easy way for caller to inspect or use
        return self

    def clear_metadata(self, field: str | None = None, value=None) -> None:
        if field is None:
            self.metadata = {}
        elif field in self.metadata:
            if value is None:
                self.metadata.pop(field)
            else:
                updated = []
                for v in self.metadata[field]:
                    if v != value:
                        updated.append(v)
                self.metadata[field] = updated

    def as_dict(self) -> dict[str, Any]:
        """
        Return custom dict of this DSpaceObject with specific attributes included (no _links, etc.)
        @return: dict of this DSpaceObject for API use
        """
        return {
            'uuid': self.uuid,
            'name': self.name,
            'handle': self.handle,
            'metadata': self.metadata,
            'lastModified': self.lastModified,
            'type': self.type,
        }

    def to_json(self) -> str:
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=None)

    def to_json_pretty(self) -> str:
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)


class SimpleDSpaceObject(DSpaceObject):
    """
    Objects that share similar simple API methods eg. PUT update for full metadata replacement, can have handles, etc.
    By default this is Item, Community, Collection classes
    """


class Item(SimpleDSpaceObject):
    """
    Extends DSpaceObject to implement specific attributes and functions for items
    """
    inArchive: bool
    discoverable: bool
    withdrawn: bool

    def __init__(
        self,
        api_resource: dict[str, Any] | None = None,
        dso: DSpaceObject | None = None,
    ) -> None:
        """
        Default constructor. Call DSpaceObject init then set item-specific attributes
        @param api_resource: API result object to use as initial data
        """
        if dso is not None:
            api_resource = dso.as_dict()
            super().__init__(dso=dso)
        else:
            super().__init__(api_resource)

        self._init_fields(api_resource, discoverable=False, withdrawn=False)
        # inArchive is the one field whose default depends on *how* the Item was
        # built: an API resource that omits it describes an archived item, while
        # a bare Item() is not archived yet. Item is also the only subclass that
        # stamps `type` solely when built from a resource - DSpaceObject.__init__
        # has already assigned self.type, so a bare Item() keeps type None.
        self.inArchive = False
        if api_resource is not None:
            self.type = 'item'
            self.inArchive = api_resource.get('inArchive', True)

    def get_metadata_values(self, field: str) -> list:
        """
        Return metadata values as simple list of strings
        @param field: DSpace field, eg. dc.creator
        @return: list of strings
        """
        values = []
        if field in self.metadata:
            values = self.metadata[field]
        return values

    def as_dict(self) -> dict[str, Any]:
        """
        Return a dict representation of this Item, based on super with item-specific attributes added
        @return: dict of Item for API use
        """
        dso_dict = super().as_dict()
        item_dict = {'inArchive': self.inArchive,
                     'discoverable': self.discoverable, 'withdrawn': self.withdrawn}
        return {**dso_dict, **item_dict}

    @classmethod
    def from_dso(cls, dso: DSpaceObject) -> Item:
        # Create new Item and copy everything over from this dso
        item = cls()
        item.__dict__.update(deepcopy(dso.__dict__))
        return item


class Community(SimpleDSpaceObject):
    """
    Extends DSpaceObject to implement specific attributes and functions for communities
    """

    def __init__(self, api_resource: dict[str, Any] | None = None) -> None:
        """
        Default constructor. Call DSpaceObject init then set item-specific attributes
        @param api_resource: API result object to use as initial data
        """
        super().__init__(api_resource)
        self.type = 'community'


class Collection(SimpleDSpaceObject):
    """
    Extends DSpaceObject to implement specific attributes and functions for collections
    """

    def __init__(self, api_resource: dict[str, Any] | None = None) -> None:
        """
        Default constructor. Call DSpaceObject init then set collection-specific attributes
        @param api_resource: API result object to use as initial data
        """
        super().__init__(api_resource)
        self.type = 'collection'


class Bundle(DSpaceObject):
    """
    Extends DSpaceObject to implement specific attributes and functions for bundles
    """

    def __init__(self, api_resource: dict[str, Any] | None = None) -> None:
        """
        Default constructor. Call DSpaceObject init then set bundle-specific attributes
        @param api_resource: API result object to use as initial data
        """
        super().__init__(api_resource)
        self.type = 'bundle'


class Bitstream(DSpaceObject):
    """
    Extends DSpaceObject to implement specific attributes and functions for bundles
    """
    # Bitstream has a few extra fields specific to file storage
    bundleName: str | None
    sizeBytes: int | None
    checkSum: dict[str, Any]
    sequenceId: int | None

    def __init__(self, api_resource: dict[str, Any] | None = None) -> None:
        """
        Default constructor. Call DSpaceObject init then set bitstream-specific attributes
        @param api_resource: API result object to use as initial data
        """
        super().__init__(api_resource)
        self.type = 'bitstream'
        self._init_fields(api_resource, bundleName=None, sizeBytes=None,
                          sequenceId=None)
        self._init_fields(api_resource, _shallow,
                          checkSum={'checkSumAlgorithm': 'MD5', 'value': None})

    def as_dict(self) -> dict[str, Any]:
        """
        Return a dict representation of this Bitstream, based on super with bitstream-specific attributes added
        @return: dict of Bitstream for API use
        """
        dso_dict = super().as_dict()
        bitstream_dict = {'bundleName': self.bundleName, 'sizeBytes': self.sizeBytes, 'checkSum': self.checkSum,
                          'sequenceId': self.sequenceId}
        return {**dso_dict, **bitstream_dict}


class Group(DSpaceObject):
    """
    Extends DSpaceObject to implement specific attributes and methods for groups (aka. EPersonGroups)
    """
    permanent: bool

    def __init__(self, api_resource: dict[str, Any] | None = None) -> None:
        """
        Default constructor. Call DSpaceObject init then set group-specific attributes
        @param api_resource: API result object to use as initial data
        """
        super().__init__(api_resource)
        self.type = 'group'
        self._init_fields(api_resource, name=None, permanent=False)

    def as_dict(self) -> dict[str, Any]:
        """
        Return a dict representation of this Group, based on super with group-specific attributes added
        @return: dict of Group for API use
        """
        dso_dict = super().as_dict()
        group_dict = {'name': self.name, 'permanent': self.permanent}
        return {**dso_dict, **group_dict}


class User(SimpleDSpaceObject):
    """
    Extends DSpaceObject to implement specific attributes and methods for users (aka. EPersons)
    """
    netid: str | None
    lastActive: Any
    canLogIn: bool
    email: str | None
    requireCertificate: bool
    selfRegistered: bool

    def __init__(self, api_resource: dict[str, Any] | None = None) -> None:
        """
        Default constructor. Call DSpaceObject init then set user-specific attributes
        @param api_resource: API result object to use as initial data
        """
        super().__init__(api_resource)
        self.type = 'user'
        self._init_fields(api_resource, name=None, netid=None, lastActive=None,
                          canLogIn=False, email=None, requireCertificate=False,
                          selfRegistered=False)

    def as_dict(self) -> dict[str, Any]:
        """
        Return a dict representation of this User, based on super with user-specific attributes added
        @return: dict of User for API use
        """
        dso_dict = super().as_dict()
        user_dict = {'name': self.name, 'netid': self.netid, 'lastActive': self.lastActive, 'canLogIn': self.canLogIn,
                     'email': self.email, 'requireCertificate': self.requireCertificate,
                     'selfRegistered': self.selfRegistered}
        return {**dso_dict, **user_dict}


class InProgressSubmission(AddressableHALResource):
    lastModified: Any
    step: Any
    sections: dict[str, Any]

    def __init__(self, api_resource: dict[str, Any] | None = None) -> None:
        super().__init__(api_resource)
        self._init_fields(api_resource, lastModified=None, step=None, type=None)
        self._init_fields(api_resource, _shallow, sections={})

    def as_dict(self) -> dict[str, Any]:
        parent_dict = super().as_dict()
        submission_dict = {
            'lastModified': self.lastModified,
            'step': self.step,
            'sections': self.sections,
            'type': self.type
        }
        return {**parent_dict, **submission_dict}


class WorkspaceItem(InProgressSubmission):
    pass


class EntityType(AddressableHALResource):
    """
    Extends Addressable HAL Resource to model an entity type (aka item type)
    used in entities and relationships. For example, Publication, Person, Project and Journal
    are all common entity types used in DSpace 7+
    """

    label: Any

    def __init__(self, api_resource: dict[str, Any]) -> None:
        super().__init__(api_resource)
        self._init_fields(api_resource, label=None, type=None)


class RelationshipType(AddressableHALResource):
    """
    TODO: RelationshipType
    """

    def __init__(self, api_resource: dict[str, Any]) -> None:
        super().__init__(api_resource)


class License(AddressableHALResource):
    """
    Specific attributes and functions for licenses
    """
    name: str | None
    definition: str | None
    confirmation: int
    requiredInfo: str | None
    licenseLabel: Label | None
    extendedLicenseLabel: list[Label]
    bitstream: Any

    def __init__(self, api_resource: dict[str, Any] | None = None) -> None:
        super().__init__(api_resource)
        api_resource = api_resource or {}
        self.type = 'clarinlicense'
        self._init_fields(api_resource, name=None, definition=None,
                          confirmation=0, requiredInfo=None)
        license_label_value = api_resource.get('clarinLicenseLabel')
        self.licenseLabel = Label(license_label_value) if license_label_value else None
        self.extendedLicenseLabel = [Label(label) for label in
                                     api_resource.get('extendedClarinLicenseLabels', [])]
        self.bitstream = api_resource.get('bitstreams')

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'license_id': self.id,
            'definition': self.definition,
            'confirmation': self.confirmation,
            'required_info': self.requiredInfo,
            'label_id': self.licenseLabel.id if self.licenseLabel else None,
        }


class Label(AddressableHALResource):
    """
    Specific attributes and functions for licenses
    """
    label: str | None
    title: str | None
    icon: str | None
    extended: bool

    def __init__(self, api_resource: dict[str, Any] | None = None) -> None:
        """
        Default constructor. Call DSpaceObject init then set label-specific attributes
        @param api_resource: API result object to use as initial data
        """
        super().__init__(api_resource)
        self.type = 'clarinlicenselabel'
        self._init_fields(api_resource, label=None, title=None, icon=None,
                          extended=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            'label_id': self.id,
            'label': self.label,
            'title': self.title,
            'icon': self.icon,
            'is_extended': self.extended
        }


class ResourcePolicy(AddressableHALResource):
    """
        DQ specific. Extends Addressable HAL Resource to model a resource policy.
    """
    name: str | None
    description: str | None
    startDate: str | None
    endDate: str | None
    action: str | None
    policyType: str | None
    groupName: str | None
    groupUUID: str | None

    def __init__(self, api_resource: dict[str, Any]) -> None:
        super().__init__(api_resource)
        api_resource = api_resource or {}
        # groupName / groupUUID come straight off a cached as_dict(); the live
        # API instead nests the group under _embedded (handled below).
        self._init_fields(api_resource, name=None, description=None,
                          startDate=None, endDate=None, type=None, action=None,
                          policyType=None, groupName=None, groupUUID=None)
        # If not found, try extracting from _embedded structure (live API format)
        if self.groupName is None and '_embedded' in api_resource:
            if 'group' in api_resource['_embedded']:
                self.groupName = api_resource['_embedded']['group'].get('name')
                self.groupUUID = api_resource['_embedded']['group'].get('uuid')

    def as_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'description': self.description,
            'startDate': self.startDate,
            'endDate': self.endDate,
            'action': self.action,
            'policyType': self.policyType,
            'groupName': self.groupName,
            'groupUUID': self.groupUUID,
        }

    def __repr__(self) -> str:
        return f"ResourcePolicy: {self.name} [{self.groupName}] [action: {self.action}] [type: {self.type}]"
