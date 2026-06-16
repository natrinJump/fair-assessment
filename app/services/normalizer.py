import json
import re
import xml.etree.ElementTree as ET
from app.models.metadata import CoreMetadata, NormalizedMetadata


VOCAB_URI_PATTERNS = {
    'agrovoc': 'agrovoc',
    'aims.fao.org': 'agrovoc',
    'agrovoc.fao.org': 'agrovoc',
    'id.nlm.nih.gov/mesh': 'mesh',
    'nlm.nih.gov': 'mesh',
    'meshb.nlm': 'mesh',
    'purl.obolibrary.org/obo/envo': 'envo',
    'ddialliance.org': 'ddi',
    'purl.org/dc': 'Dublin Core, dcterms:',
    'schema.org': 'schema.org',
    'w3.org/ns/dcat': 'DCAT, dcat:',
    'w3.org/2004/02/skos': 'SKOS, skos:',
}
 
def extract_vocab_indicators(subjects: list) -> str:
    """
    Extract vocabulary indicators from DataCite subjects list.
    Each subject may have subjectScheme, schemeUri, valueUri.
    Returns a comma-separated string of detected vocabulary names
    that the backend check_vocabulary() will find.
    """
    found = set()
    for s in subjects:
        for field in ['subjectScheme', 'schemeURI', 'schemeUri', 'valueURI', 'valueUri']:
            val = s.get(field, '').lower()
            if not val:
                continue
            # Add the raw value so it can be matched against profile.required_vocabulary
            found.add(val)
            # Also map to known vocab names
            for pattern, name in VOCAB_URI_PATTERNS.items():
                if pattern in val:
                    for n in name.split(','):
                        found.add(n.strip())
    return ', '.join(found)


def extract_custom_fields(attrs: dict, custom_fields: list) -> dict:
    custom = {}
    if not custom_fields:
        return custom

    subjects = attrs.get("subjects", [])
    descriptions = attrs.get("descriptions", [])
    geo_locations = attrs.get("geoLocations", [])

    search_text = str(attrs).lower()

    for field in custom_fields:
        field_lower = field.lower()

        if field_lower in ["spatial_coverage", "spatial coverage",
                           "location", "geolocation"]:
            if geo_locations:
                place = geo_locations[0].get("geoLocationPlace", "")
                if place:
                    custom[field] = place
                    continue

        elif field_lower in ["crop_type", "crop type", "crop"]:
            for s in subjects:
                val = s.get("subject", "")
                if any(kw in val.lower() for kw in
                       ["wheat", "maize", "rice", "crop", "plant",
                        "agricultural"]):
                    custom[field] = val
                    break

        elif field_lower in ["organism", "species", "taxon"]:
            for s in subjects:
                val = s.get("subject", "")
                if any(kw in val.lower() for kw in
                       ["organism", "species", "taxon", "genus",
                        "bacteria", "virus", "human", "mouse"]):
                    custom[field] = val
                    break

        elif field_lower in ["experimental_method", "method", "methodology"]:
            for d in descriptions:
                if d.get("descriptionType") in ["Methods", "TechnicalInfo"]:
                    custom[field] = d.get("description", "")[:200]
                    break

        elif field_lower in ["temporal_coverage", "time period", "date range"]:
            dates = attrs.get("dates", [])
            for d in dates:
                if d.get("dateType") in ["Collected", "Coverage"]:
                    custom[field] = d.get("date", "")
                    break

        if field not in custom:
            for s in subjects:
                val = s.get("subject", "")
                if field_lower in val.lower():
                    custom[field] = val
                    break

    return custom


def normalize_datacite(raw: dict, doi: str,
                       custom_fields: list = None) -> NormalizedMetadata:
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

    related = attrs.get("relatedIdentifiers", [])
    custom = extract_custom_fields(attrs, custom_fields or [])
    if related:
        custom["_related_identifiers"] = str(related)[:500]

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
        core=core,
        custom=custom
    )


def normalize_zenodo(raw: dict, identifier: str,
                     custom_fields: list = None) -> NormalizedMetadata:
    data = raw.get("data", {})
    metadata = data.get("metadata", data)

    creators = metadata.get("creators", [])
    creator = creators[0].get("name") if creators else None

    license_info = metadata.get("license", {})
    if isinstance(license_info, dict):
        license_val = license_info.get("id") or license_info.get("title")
    else:
        license_val = str(license_info) if license_info else None

    formats = []
    for f in data.get("files", []):
        ext = f.get("key", "").split(".")[-1].lower()
        if ext and ext not in formats:
            formats.append(ext)

    related = metadata.get("related_identifiers", [])
    custom = {}
    if related:
        custom["_related_identifiers"] = str(related)[:500]

    if custom_fields:
        subjects = metadata.get("subjects", [])
        keywords = metadata.get("keywords", [])
        all_terms = [s.get("term", s) if isinstance(s, dict)
                     else str(s) for s in subjects + keywords]
        for field in custom_fields:
            for term in all_terms:
                if field.lower().replace("_", " ") in term.lower():
                    custom[field] = term
                    break

    core = CoreMetadata(
        identifier=str(data.get("doi") or
                       data.get("conceptdoi") or identifier),
        title=metadata.get("title"),
        description=metadata.get("description"),
        creator=creator,
        license=license_val,
        formats=formats,
        access_url=data.get("links", {}).get("html") or
                   f"https://zenodo.org/record/{data.get('id', '')}",
        provenance_date=str(metadata.get("publication_date") or
                            metadata.get("created", ""))[:4] or None,
    )
    return NormalizedMetadata(
        source="zenodo",
        raw_identifier=identifier,
        core=core,
        custom=custom
    )


def normalize_schema_org(raw: dict, identifier: str,
                         custom_fields: list = None) -> NormalizedMetadata:
    data = raw.get("data", {})

    if "@graph" in data:
        for item in data["@graph"]:
            if "Dataset" in str(item.get("@type", "")):
                data = item
                break

    def get_name(val):
        if isinstance(val, list):
            val = val[0]
        if isinstance(val, dict):
            return val.get("name") or val.get("@id")
        return str(val) if val else None

    creators = data.get("creator") or data.get("author") or []
    if isinstance(creators, dict):
        creators = [creators]
    creator = get_name(creators[0]) if creators else None

    license_val = data.get("license")
    if isinstance(license_val, dict):
        license_val = license_val.get("@id") or license_val.get("name")

    formats = []
    distribution = data.get("distribution", [])
    if isinstance(distribution, dict):
        distribution = [distribution]
    for d in distribution:
        if isinstance(d, dict):
            fmt = d.get("encodingFormat") or d.get("fileFormat")
            if fmt and fmt not in formats:
                formats.append(fmt)

    date = (data.get("datePublished") or
            data.get("dateCreated") or
            data.get("dateModified") or "")

    doi = data.get("identifier") or data.get("@id") or identifier
    if isinstance(doi, list):
        doi = doi[0]
    if isinstance(doi, dict):
        doi = doi.get("value") or doi.get("@id") or identifier

    access_url = (data.get("url") or data.get("@id") or
                  f"https://doi.org/{identifier}")

    custom = {}
    keywords = data.get("keywords", "")
    if isinstance(keywords, list):
        keywords = ", ".join(keywords)
    if custom_fields and keywords:
        for field in custom_fields:
            if field.lower().replace("_", " ") in keywords.lower():
                custom[field] = keywords

    core = CoreMetadata(
        identifier=str(doi),
        title=data.get("name") or data.get("headline"),
        description=data.get("description"),
        creator=creator,
        license=str(license_val) if license_val else None,
        formats=formats[:5],
        access_url=str(access_url),
        provenance_date=str(date)[:4] if date else None,
    )
    return NormalizedMetadata(
        source="schema_org",
        raw_identifier=identifier,
        core=core,
        custom=custom
    )


def normalize_dataverse(raw: dict, identifier: str,
                        custom_fields: list = None) -> NormalizedMetadata:
    data = raw.get("data", {})
    latest = data.get("latestVersion", data)
    fields = latest.get("metadataBlocks", {})
    citation = fields.get("citation", {}).get("fields", [])

    def get_field(name):
        for f in citation:
            if f.get("typeName") == name:
                val = f.get("value")
                if isinstance(val, list) and val:
                    first = val[0]
                    if isinstance(first, dict):
                        for v in first.values():
                            if isinstance(v, dict):
                                return v.get("value")
                            return v
                    return first
                return val
        return None

    authors = []
    for f in citation:
        if f.get("typeName") == "author":
            for a in f.get("value", []):
                name = a.get("authorName", {}).get("value")
                if name:
                    authors.append(name)

    license_info = latest.get("license", {})
    license_val = (license_info.get("name") if
                   isinstance(license_info, dict) else str(license_info))

    core = CoreMetadata(
        identifier=data.get("persistentUrl") or identifier,
        title=get_field("title"),
        description=get_field("dsDescription"),
        creator=authors[0] if authors else None,
        license=license_val,
        formats=[],
        access_url=data.get("persistentUrl") or
                   f"https://doi.org/{identifier}",
        provenance_date=get_field("productionDate") or
                        get_field("distributionDate"),
    )
    return NormalizedMetadata(
        source="dataverse",
        raw_identifier=identifier,
        core=core,
        custom={}
    )


def normalize_content_negotiation(raw: dict, identifier: str,
                                  custom_fields: list = None
                                  ) -> NormalizedMetadata:
    data = raw.get("data", {})
    fmt = raw.get("format", "")
    if "datacite" in fmt:
        return normalize_datacite(
            {"data": {"attributes": data}},
            identifier, custom_fields
        )
    return normalize_schema_org(raw, identifier, custom_fields)


def normalize_generic(raw: dict, doi: str,
                      custom_fields: list = None) -> NormalizedMetadata:
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
        core=core,
        custom={}
    )


def normalize_ark(raw: dict, identifier: str,
                  custom_fields: list = None) -> NormalizedMetadata:
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
    return NormalizedMetadata(
        source="ark",
        raw_identifier=identifier,
        core=core,
        custom={}
    )


def normalize_url(raw: dict, identifier: str,
                  custom_fields: list = None) -> NormalizedMetadata:
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
    return NormalizedMetadata(
        source="url",
        raw_identifier=identifier,
        core=core,
        custom={}
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
    for field in (custom_fields or []):
        val = data.get(field)
        if val:
            custom[field] = str(val)

    # include detected vocabulary prefixes from TTL/RDF parsing
    if data.get("detected_vocabularies"):
        custom["_detected_vocabularies"] = data["detected_vocabularies"]
        
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

    return _normalize_json_upload(
        data,
        data.get("identifier", "uploaded-file"),
        custom_fields
    )