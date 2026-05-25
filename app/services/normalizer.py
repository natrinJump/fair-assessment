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

    formats = attrs.get("formats", [])

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