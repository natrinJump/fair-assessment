from app.models.metadata import CoreMetadata, NormalizedMetadata

def normalize_datacite(raw: dict, doi: str) -> NormalizedMetadata:
    # handle both {"data": {"attributes": ...}} and direct {"attributes": ...}
    data = raw.get("data", raw)
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    attrs = data.get("attributes", data)

    rights = attrs.get("rightsList", [])
    license_url = rights[0].get("rightsUri") if rights else None

    creators = attrs.get("creators", [])
    creator = creators[0].get("name") if creators else None

    formats = list(set(attrs.get("formats", [])))[:5]

    titles = attrs.get("titles", [])
    title = titles[0].get("title") if titles else None

    descriptions = attrs.get("descriptions", [])
    description = descriptions[0].get("description") if descriptions else None

    identifier = attrs.get("doi") or attrs.get("identifier") or doi

    core = CoreMetadata(
        identifier=identifier,
        title=title,
        description=description,
        creator=creator,
        license=license_url,
        formats=formats,
        access_url=f"https://doi.org/{identifier}",
        provenance_date=attrs.get("published"),
    )

    return NormalizedMetadata(
        source="datacite",
        raw_identifier=doi,
        core=core
    )

def _normalize_json_upload(data: dict, identifier: str,
                           custom_fields: list) -> NormalizedMetadata:
    title = data.get("title") or data.get("name")
    description = data.get("description") or data.get("abstract")
    creator = data.get("creator") or data.get("author")
    if isinstance(creator, list):
        creator = creator[0] if creator else None
    if isinstance(creator, dict):
        creator = creator.get("name") or creator.get("creatorName")
    license_val = data.get("license") or data.get("rights")
    if isinstance(license_val, dict):
        license_val = license_val.get("url") or license_val.get("rightsUri")
    formats = data.get("formats") or []
    if isinstance(formats, str):
        formats = [formats]
    date = data.get("provenance_date") or data.get("publicationYear")
    access_url = data.get("access_url") or data.get("url")

    custom = {}
    for field in custom_fields:
        val = data.get(field)
        if val:
            custom[field] = str(val)

    core = CoreMetadata(
        identifier=str(identifier),
        title=str(title) if title else None,
        description=str(description) if description else None,
        creator=str(creator) if creator else None,
        license=str(license_val) if license_val else None,
        formats=formats[:5],
        access_url=str(access_url) if access_url else None,
        provenance_date=str(date)[:4] if date else None,
    )
    return NormalizedMetadata(
        source="upload",
        raw_identifier=str(identifier),
        core=core,
        custom=custom
    )

def normalize_from_dict(data: dict,
                        profile_name: str = None) -> NormalizedMetadata:
    """
    Normalize a pre-parsed metadata dictionary.
    Called when user uploads a file — parsing happens on frontend.
    """
    custom_fields = []
    if profile_name:
        try:
            from app.services.profile_service import (
                get_profile_by_domain, get_profile_by_name
            )
            p = get_profile_by_domain(profile_name)
            if not p:
                p = get_profile_by_name(profile_name)
            if p:
                custom_fields = (
                    p.get("custom_metadata_fields", []) +
                    p.get("required_metadata_fields", [])
                )
        except Exception:
            pass

    return _normalize_json_upload(data, data.get("identifier", "uploaded-file"), custom_fields)

def normalize_generic(raw: dict, doi: str) -> NormalizedMetadata:
    data = raw.get("data", {})

    core = CoreMetadata(
        identifier=doi,
        title=data.get("title"),
        description=data.get("description"),
        creator=data.get("creator"),
        license=data.get("license"),
        formats=[],
        access_url=f"https://doi.org/{doi}",
        provenance_date=None,
    )

    return NormalizedMetadata(
        source="generic",
        raw_identifier=doi,
        core=core
    )

def normalize_ark(raw: dict, identifier: str) -> NormalizedMetadata:
    data = raw.get("data", {})
    core = CoreMetadata(
        identifier=identifier,
        title=data.get("title"),
        description=data.get("description"),
        creator=data.get("creator"),
        license=data.get("license"),
        formats=data.get("formats", []),
        access_url=data.get("access_url", f"https://n2t.net/{identifier}"),
        provenance_date=data.get("provenance_date"),
    )
    return NormalizedMetadata(source="ark", raw_identifier=identifier, core=core)

def normalize_url(raw: dict, identifier: str) -> NormalizedMetadata:
    data = raw.get("data", {})
    core = CoreMetadata(
        identifier=identifier,
        title=data.get("title"),
        description=data.get("description"),
        creator=data.get("creator"),
        license=data.get("license"),
        formats=data.get("formats", []),
        access_url=data.get("access_url", identifier),
        provenance_date=data.get("provenance_date"),
    )
    return NormalizedMetadata(source="url", raw_identifier=identifier, core=core)