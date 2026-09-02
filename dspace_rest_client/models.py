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

from copy import deepcopy
import json
from typing import Any


__all__ = [
    'HALResource', 'AddressableHALResource', 'ExternalDataObject', 'DSpaceObject',
    'SimpleDSpaceObject', 'Item', 'Community', 'Collection', 'Bundle', 'Bitstream',
    'Group', 'User', 'InProgressSubmission', 'WorkspaceItem', 'EntityType',
    'RelationshipType', 'License', 'Label', 'ResourcePolicy',
]


class HALResource:
    """
    Base class to represent HAL+JSON API resources
    """
    links: dict[str, Any]
    type: str | None = None

    def __init__(self, api_resource: dict[str, Any] | None = None) -> None:
        """
        Default constructor
        @param api_resource: optional API resource (JSON) from a GET response or successful POST can populate instance
        """
        self._from_d: dict[str, Any] | None = None
        self.links: dict[str, Any] = {}
        self.embedded: dict[str, Any] = {}
        if api_resource is not None:
            self._from_d = api_resource
            if 'type' in api_resource:
                self.type = api_resource['type']
            if '_links' in api_resource:
                self.links = deepcopy(api_resource['_links'])
            else:
                self.links = {'self': {'href': None}}
            if '_embedded' in api_resource:
                self.embedded = deepcopy(api_resource['_embedded'])


class AddressableHALResource(HALResource):
    id: Any = None

    def __init__(self, api_resource: dict[str, Any] | None = None) -> None:
        super().__init__(api_resource)
        if api_resource is not None:
            if 'id' in api_resource:
                self.id = api_resource['id']

    def as_dict(self) -> dict[str, Any]:
        return {'id': self.id}


class ExternalDataObject(HALResource):
    """
    Generic External Data Object as configured in DSpace's external data providers framework
    """
    id: Any = None
    display: Any = None
    value: Any = None
    externalSource: Any = None
    metadata: dict[str, Any]

    def __init__(self, api_resource: dict[str, Any] | None = None) -> None:
        """
        Default constructor
        @param api_resource: optional API resource (JSON) from a GET response or successful POST can populate instance
        """
        super().__init__(api_resource)

        self.metadata: dict[str, Any] = {}

        if api_resource is not None:
            if 'id' in api_resource:
                self.id = api_resource['id']
            if 'display' in api_resource:
                self.display = api_resource['display']
            if 'value' in api_resource:
                self.value = api_resource['value']
            if 'externalSource' in api_resource:
                self.externalSource = api_resource['externalSource']
            if 'metadata' in api_resource:
                self.metadata = deepcopy(api_resource['metadata'])

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
    uuid: str | None = None
    name: str | None = None
    handle: str | None = None
    metadata: dict[str, Any]
    lastModified: Any = None
    type: str | None = None
    parent: Any = None

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
        self.type = None
        self.metadata: dict[str, Any] = {}

        if dso is not None:
            api_resource = dso.as_dict()
            self.links = deepcopy(dso.links)
        if api_resource is not None:
            if 'id' in api_resource:
                self.id = api_resource['id']
            if 'uuid' in api_resource:
                self.uuid = api_resource['uuid']
            if 'type' in api_resource:
                self.type = api_resource['type']
            if 'name' in api_resource:
                self.name = api_resource['name']
            if 'handle' in api_resource:
                self.handle = api_resource['handle']
            if 'metadata' in api_resource:
                self.metadata = deepcopy(api_resource['metadata'])
            # Python interprets _ prefix as private so for now, renaming this and handling it separately
            # alternatively - each item could implement getters, or a public method to return links
            if '_links' in api_resource:
                self.links = deepcopy(api_resource['_links'])

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
    type = 'item'
    inArchive = False
    discoverable = False
    withdrawn = False

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

        if api_resource is not None:
            self.type = 'item'
            self.inArchive = api_resource['inArchive'] if 'inArchive' in api_resource else True
            self.discoverable = api_resource['discoverable'] if 'discoverable' in api_resource else False
            self.withdrawn = api_resource['withdrawn'] if 'withdrawn' in api_resource else False

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
    type = 'community'

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
    type = 'collection'

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
    type = 'bundle'

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
    type = 'bitstream'
    # Bitstream has a few extra fields specific to file storage
    bundleName: str | None = None
    sizeBytes: int | None = None
    checkSum: dict[str, Any]
    sequenceId: int | None = None

    def __init__(self, api_resource: dict[str, Any] | None = None) -> None:
        """
        Default constructor. Call DSpaceObject init then set bitstream-specific attributes
        @param api_resource: API result object to use as initial data
        """
        super().__init__(api_resource)
        self.type = 'bitstream'
        self.bundleName = None
        self.sizeBytes = None
        self.checkSum = {'checkSumAlgorithm': 'MD5', 'value': None}
        self.sequenceId = None
        api_resource = api_resource or {}
        if 'bundleName' in api_resource:
            self.bundleName = api_resource['bundleName']
        if 'sizeBytes' in api_resource:
            self.sizeBytes = api_resource['sizeBytes']
        if 'checkSum' in api_resource:
            self.checkSum = api_resource['checkSum'].copy()
        if 'sequenceId' in api_resource:
            self.sequenceId = api_resource['sequenceId']

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
    type = 'group'
    name = None
    permanent = False

    def __init__(self, api_resource: dict[str, Any] | None = None) -> None:
        """
        Default constructor. Call DSpaceObject init then set group-specific attributes
        @param api_resource: API result object to use as initial data
        """
        super().__init__(api_resource)
        self.type = 'group'
        self.name = None
        self.permanent = False
        api_resource = api_resource or {}
        if 'name' in api_resource:
            self.name = api_resource['name']
        if 'permanent' in api_resource:
            self.permanent = api_resource['permanent']

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
    type = 'user'
    name = None
    netid = None
    lastActive = None
    canLogIn = False
    email = None
    requireCertificate = False
    selfRegistered = False

    def __init__(self, api_resource: dict[str, Any] | None = None) -> None:
        """
        Default constructor. Call DSpaceObject init then set user-specific attributes
        @param api_resource: API result object to use as initial data
        """
        super().__init__(api_resource)
        self.type = 'user'
        self.name = None
        self.netid = None
        self.lastActive = None
        self.canLogIn = False
        self.email = None
        self.requireCertificate = False
        self.selfRegistered = False
        api_resource = api_resource or {}
        if 'name' in api_resource:
            self.name = api_resource['name']
        if 'netid' in api_resource:
            self.netid = api_resource['netid']
        if 'lastActive' in api_resource:
            self.lastActive = api_resource['lastActive']
        if 'canLogIn' in api_resource:
            self.canLogIn = api_resource['canLogIn']
        if 'email' in api_resource:
            self.email = api_resource['email']
        if 'requireCertificate' in api_resource:
            self.requireCertificate = api_resource['requireCertificate']
        if 'selfRegistered' in api_resource:
            self.selfRegistered = api_resource['selfRegistered']

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
    lastModified: Any = None
    step: Any = None
    sections: dict[str, Any]
    type: str | None = None

    def __init__(self, api_resource: dict[str, Any] | None = None) -> None:
        super().__init__(api_resource)
        self.lastModified = None
        self.step = None
        self.sections: dict[str, Any] = {}
        self.type = None
        api_resource = api_resource or {}
        if 'lastModified' in api_resource:
            self.lastModified = api_resource['lastModified']
        if 'step' in api_resource:
            self.step = api_resource['step']
        if 'sections' in api_resource:
            self.sections = api_resource['sections'].copy()
        if 'type' in api_resource:
            self.type = api_resource['type']

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

    def __init__(self, api_resource: dict[str, Any]) -> None:
        super().__init__(api_resource)
        if 'label' in api_resource:
            self.label = api_resource['label']
        if 'type' in api_resource:
            self.type = api_resource['type']


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

    def __init__(self, api_resource: dict[str, Any] | None = None) -> None:
        super().__init__(api_resource)
        api_resource = api_resource or {}
        self.type = 'clarinlicense'
        self.name = api_resource.get('name')
        self.definition = api_resource.get('definition')
        self.confirmation = api_resource.get('confirmation', 0)
        self.requiredInfo = api_resource.get('requiredInfo')
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

    def __init__(self, api_resource: dict[str, Any] | None = None) -> None:
        """
        Default constructor. Call DSpaceObject init then set label-specific attributes
        @param api_resource: API result object to use as initial data
        """
        super().__init__(api_resource)
        api_resource = api_resource or {}
        self.type = 'clarinlicenselabel'
        self.label = api_resource.get('label')
        self.title = api_resource.get('title')
        self.icon = api_resource.get('icon')
        self.extended = api_resource.get('extended', False)

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

    def __init__(self, api_resource: dict[str, Any]) -> None:
        super().__init__(api_resource)
        api_resource = api_resource or {}
        self.name = api_resource.get('name')
        self.description = api_resource.get('description')
        self.startDate = api_resource.get('startDate')
        self.endDate = api_resource.get('endDate')
        self.type = api_resource.get('type')
        self.action = api_resource.get('action')
        self.policyType = api_resource.get('policyType')
        # Check for direct groupName/groupUUID (cached format from as_dict())
        self.groupName = api_resource.get('groupName')
        self.groupUUID = api_resource.get('groupUUID')
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
