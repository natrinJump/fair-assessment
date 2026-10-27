import json
import os
import re
from app.models.metadata import NormalizedMetadata
from app.models.profile import Profile, MetricResult, AssessmentReport


# ─── SPDX license identifiers (common subset) ─────────────────────────────────
# F-UJI validates R1.1 against this list. Keep it broad enough to match
# Creative Commons URIs and common open-source/open-data identifiers.
SPDX_LICENSES = {
    # Creative Commons
    "cc0-1.0", "cc-by-4.0", "cc-by-3.0", "cc-by-2.0", "cc-by-1.0",
    "cc-by-sa-4.0", "cc-by-sa-3.0", "cc-by-nc-4.0", "cc-by-nd-4.0",
    "cc-by-nc-nd-4.0", "cc-by-nc-sa-4.0",
    # Open source
    "mit", "apache-2.0", "gpl-2.0", "gpl-2.0-only", "gpl-2.0-or-later",
    "gpl-3.0-only", "gpl-3.0-or-later", "lgpl-2.1", "lgpl-3.0-or-later",
    "bsd-2-clause", "bsd-3-clause", "isc", "mpl-2.0",
    "agpl-3.0-only", "agpl-3.0-or-later",
    # Open data / government
    "odc-by", "odbl-1.0", "pddl-1.0", "ogl-canada-2.0",
    # Other
    "eupl-1.2", "epl-2.0", "epl-1.0",
}

# URI fragments that are sufficient evidence of a machine-readable,
# SPDX-resolvable licence even without exact ID matching.
SPDX_URI_FRAGMENTS = [
    "spdx.org/licenses/",
    "creativecommons.org/licenses/",
    "creativecommons.org/publicdomain/zero/",
    "opensource.org/licenses/",
    "opendatacommons.org/licenses/",
]

# ─── Registered vocabulary namespaces (F-UJI I2 style) ───────────────────────
# F-UJI detects semantic resources by scanning metadata for known ontology
# namespace URIs rather than keyword matching.  A subset of commonly indexed
# namespaces is listed here; extend as needed.
KNOWN_VOCAB_NAMESPACES: dict = {
    "schema.org":    ["http://schema.org/", "https://schema.org/",
                      "http://schema.org", "https://schema.org"],
    "DCAT":          ["http://www.w3.org/ns/dcat", "https://www.w3.org/ns/dcat"],
    "Dublin Core":   ["http://purl.org/dc/", "http://dublincore.org/"],
    "SKOS":          ["http://www.w3.org/2004/02/skos/"],
    "PROV-O":        ["http://www.w3.org/ns/prov"],
    "OBO Library":   ["http://purl.obolibrary.org/obo/"],
    "RDF":           ["http://www.w3.org/1999/02/22-rdf-syntax-ns#"],
    "OWL":           ["http://www.w3.org/2002/07/owl#"],
    "FOAF":          ["http://xmlns.com/foaf/"],
    "Wikidata":      ["http://www.wikidata.org/"],
    "GeoNames":      ["http://sws.geonames.org/", "http://www.geonames.org/"],
    "MeSH":          ["http://id.nlm.nih.gov/mesh/"],
    "AGROVOC":       ["http://aims.fao.org/aos/agrovoc/"],
    "Gene Ontology": ["http://purl.obolibrary.org/obo/GO_"],
    "ENVO":          ["http://purl.obolibrary.org/obo/ENVO_"],
    "DataCite":      ["http://datacite.org/schema/"],
    "BioPortal":     ["http://bioportal.bioontology.org/"],
    "EBI":           ["http://www.ebi.ac.uk/"],
}

# PROV/PAV URIs used by FsF-R1.2-01M-2
PROV_ONTOLOGY_URIS = [
    "http://www.w3.org/ns/prov",
    "https://www.w3.org/ns/prov",
    "http://purl.org/pav",
    "https://purl.org/pav",
]

# Community metadata standards — namespace/URI patterns used by check_r1_3()
# when profile.required_community_standards is non-empty.
# Keys are lowercase standard names; values are substrings to scan for in
# the raw metadata text (case-insensitive).  Add new standards here as needed.
COMMUNITY_STANDARDS_PATTERNS: dict = {
    "schema.org":       ["schema.org/", "http://schema.org", "https://schema.org"],
    "datacite":         ["datacite.org/schema", "datacite.org"],
    "dublin core":      ["purl.org/dc/", "dublincore.org"],
    "dcat":             ["w3.org/ns/dcat", "dcat:"],
    "dcat-ap":          ["dcat-ap", "joinup.ec.europa.eu/collection/semantic-interoperability"],
    "ddi":              ["ddialliance.org", "ddi:", "colectica"],
    "abcd":             ["tdwg.org/schemas/abcd", "abcd:"],
    "darwin core":      ["rs.tdwg.org/dwc/", "dwc:", "darwincore"],
    "iso 19115":        ["iso19115", "iso 19115", "19115-"],
    "cf conventions":   ["cfconventions.org", "cf-1.", ":Conventions"],
    "inspire":          ["inspire.ec.europa.eu"],
    "eml":              ["eml.ecoinformatics.org", "<eml:"],
    "europeana edm":    ["europeana.eu/schemas/edm", "edm:"],
    "marc":             ["loc.gov/marc/", "marc:"],
    "oai-pmh":          ["openarchives.org/oai/"],
    "codemeta":         ["codemeta.github.io", "codemeta:"],
    "bioschemas":       ["bioschemas.org"],
    "ogc":              ["opengeospatial.org", "ogc:"],
    "mixs":             ["gensc.org/mixs", "mixs:"],
}

# Content-type → format name mapping used for landing-page detection
CONTENT_TYPE_MAP = {
    "text/turtle":                   "turtle",
    "application/rdf+xml":           "rdf",
    "application/ld+json":           "json-ld",
    "application/json":              "json",
    "text/csv":                      "csv",
    "application/xml":               "xml",
    "text/xml":                      "xml",
    "application/zip":               "zip",
    "application/x-netcdf":          "netcdf",
    "application/netcdf":            "netcdf",
    "application/vnd.ms-excel":      "xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
}

# File extensions to scan for in HTML when the landing page returns HTML
HTML_EXTENSION_MAP = {
    ".csv": "csv", ".json": "json", ".jsonld": "json-ld",
    ".rdf": "rdf", ".ttl": "turtle", ".xml": "xml",
    ".nc": "netcdf", ".xlsx": "xlsx", ".zip": "zip",
    ".geojson": "json", ".parquet": "parquet",
}


def load_profile(profile_name: str) -> Profile:
    from app.services.profile_service import (
        get_profile_by_domain, get_profile_by_name
    )
    p = get_profile_by_domain(profile_name)
    if p:
        return Profile(**p)
    p = get_profile_by_name(profile_name)
    if p:
        return Profile(**p)
    path = os.path.join("profiles", "generic_fair.json")
    with open(path, "r") as f:
        return Profile(**json.load(f))


def match_identifier(identifier: str, accepted: str,
                     custom_identifiers: list) -> bool:
    id_lower = identifier.lower()
    accepted_lower = accepted.lower()

    if accepted_lower == "doi" and (
        id_lower.startswith("10.") or "doi.org/10." in id_lower
    ):
        return True
    if accepted_lower == "handle" and (
        id_lower.startswith("hdl:") or
        id_lower.startswith("20.") or
        id_lower.startswith("11.")
    ):
        return True
    if accepted_lower == "ark" and "ark:" in id_lower:
        return True
    if accepted_lower == "biosample" and (
        id_lower.startswith("samn") or id_lower.startswith("sams")
    ):
        return True
    if accepted_lower == "genbank" and (
        id_lower.startswith("nc_") or id_lower.startswith("nm_")
    ):
        return True
    if accepted_lower == "w3id" and "w3id.org" in id_lower:
        return True
    if accepted_lower == "url" and id_lower.startswith("http"):
        return True
    if accepted_lower in id_lower:
        return True

    for custom in custom_identifiers:
        match_type = custom.get("match_type", "contains")
        value = custom.get("value", "").lower()
        if not value:
            continue
        if match_type == "starts_with" and id_lower.startswith(value):
            return True
        if match_type == "contains" and value in id_lower:
            return True
        if match_type == "regex":
            try:
                if re.search(value, id_lower):
                    return True
            except re.error:
                pass

    return False


def detect_identifier_type(identifier: str) -> str:
    id_lower = identifier.lower()
    if id_lower.startswith("10.") or "doi.org/10." in id_lower:
        return "doi"
    if "ark:" in id_lower:
        return "ark"
    if id_lower.startswith(("hdl:", "20.", "11.")):
        return "handle"
    if id_lower.startswith(("samn", "sams")):
        return "biosample"
    if id_lower.startswith(("nc_", "nm_")):
        return "genbank"
    if "w3id.org" in id_lower:
        return "w3id"
    if id_lower.startswith("http"):
        return "url"
    return "unknown"


def check_vocabulary(metadata: NormalizedMetadata,
                     vocab_config: dict) -> bool:
    keywords = [k.lower() for k in vocab_config.get("keywords", [])]
    vocab_name = vocab_config.get("name", "").lower()

    search_text = (
        str(metadata.core.dict()).lower() +
        str(metadata.custom).lower()
    )

    if vocab_name and vocab_name in search_text:
        return True

    abbrev = "".join(w[0] for w in vocab_name.split() if w).lower()
    if len(abbrev) >= 2 and abbrev in search_text:
        return True

    for kw in keywords:
        if kw and kw in search_text:
            return True

    words = [w for w in vocab_name.split() if len(w) > 3]
    if words and all(w in search_text for w in words):
        return True

    return False


def is_spdx_license(license_val: str) -> bool:
    """Return True if license_val matches an SPDX ID or contains a known
    SPDX-resolvable URI fragment (F-UJI style R1.1 check)."""
    lower = license_val.lower()
    for frag in SPDX_URI_FRAGMENTS:
        if frag in lower:
            return True
    # Normalise spaces/dashes and check against the SPDX set
    normalised = lower.replace(" ", "-").strip("/")
    for spdx_id in SPDX_LICENSES:
        if spdx_id in normalised or normalised.endswith(spdx_id):
            return True
    return False


def is_license_uri(license_val: str) -> bool:
    """Return True if the license value is a URI (FAIR-Checker style)."""
    return license_val.strip().startswith(("http://", "https://"))


def fetch_landing_page_formats(url: str) -> tuple:
    """Attempt to detect data formats from a landing page URL.

    Sends a content-negotiation GET request, inspects the Content-Type
    response header, and — if the response is HTML — scans the body for
    known file extension hints in download links.

    Returns (formats: list[str], source_note: str).  Always returns
    gracefully; network errors produce an empty list and an explanation.
    """
    try:
        import requests  # type: ignore

        # Prefer RDF serialisations (FAIR-Checker / F-UJI behaviour)
        headers = {
            "Accept": (
                "text/turtle,"
                "application/rdf+xml;q=0.9,"
                "application/ld+json;q=0.8,"
                "text/html;q=0.5,"
                "*/*;q=0.3"
            ),
            "User-Agent": "ProFAIR/1.0 FAIR-Assessment-Tool",
        }
        resp = requests.get(url, headers=headers,
                            allow_redirects=True, timeout=8)
        raw_ct = resp.headers.get("content-type", "")
        ct = raw_ct.lower().split(";")[0].strip()

        formats: list = []
        source_note = f"Content-Type: {ct or 'not returned'}"

        # Direct match on content-type
        if ct in CONTENT_TYPE_MAP:
            formats.append(CONTENT_TYPE_MAP[ct])
            return formats, source_note

        # HTML response — check for embedded semantic markup first,
        # then fall back to download-link extension scan.
        if "text/html" in ct:
            body = resp.text
            html  = body.lower()

            semantic_formats: list = []

            # JSON-LD: <script type="application/ld+json"> (used by Zenodo,
            # DataCite, most schema.org repositories).
            if ('type="application/ld+json"' in html or
                    "type='application/ld+json'" in html):
                semantic_formats.append("json-ld")

            # RDFa: vocab/typeof/property attributes in HTML markup.
            # Zenodo (InvenioRDM) embeds RDFa alongside JSON-LD.
            has_rdfa = (
                ('vocab="https://schema.org' in html or
                 'vocab="http://schema.org'  in html or
                 "vocab='https://schema.org" in html or
                 "vocab='http://schema.org"  in html or
                 'typeof="schema:'           in html or
                 "typeof='schema:"           in html or
                 'property="schema:'         in html or
                 "property='schema:"         in html)
            )
            if has_rdfa:
                semantic_formats.append("rdfa")

            if semantic_formats:
                found_names = ", ".join(semantic_formats)
                source_note = (
                    f"Embedded semantic markup ({found_names}) "
                    f"found in HTML landing page ({resp.url})"
                )
                return semantic_formats, source_note

            # Fall back to scanning body for download-link file extensions
            for ext, fmt in HTML_EXTENSION_MAP.items():
                if ext in html and fmt not in formats:
                    formats.append(fmt)
            if formats:
                source_note = (
                    f"HTML download links detected on landing page "
                    f"({resp.url})"
                )
            else:
                source_note = (
                    f"Landing page is HTML but no known format "
                    f"extensions found ({resp.url})"
                )
            return formats, source_note

        return [], f"Landing page returned unrecognised content-type: {ct}"

    except Exception as exc:
        return [], f"Landing page not reachable ({type(exc).__name__})"


def get_maturity(score: float) -> tuple:
    if score >= 80:
        return (
            "Advanced",
            "Dataset demonstrates strong FAIRness. Most FAIR "
            "requirements are met. Focus on remaining gaps to "
            "reach full compliance."
        )
    elif score >= 60:
        return (
            "Intermediate",
            "Dataset meets core FAIR requirements but has notable "
            "gaps. Review failed and partial metrics and address "
            "recommendations to improve."
        )
    elif score >= 40:
        return (
            "Initial",
            "Dataset has basic FAIR elements but significant "
            "improvements are needed across multiple principles. "
            "Prioritise essential metrics first."
        )
    else:
        return (
            "Incomplete",
            "Dataset does not yet meet basic FAIR requirements. "
            "Start with essential metrics: persistent identifier, "
            "basic metadata fields, and a machine-readable license."
        )


# ─── F Metrics ────────────────────────────────────────────────

def check_f1(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    identifier = metadata.core.identifier
    if not identifier:
        return MetricResult(
            metric_id="F1",
            principle="F",
            priority="essential",
            status="fail",
            description="No persistent identifier found in metadata",
            recommendation="Add a persistent identifier. "
                f"This profile accepts: "
                f"{', '.join(profile.accepted_identifiers)}"
                + (f" and {len(profile.custom_identifiers)} custom type(s)"
                   if profile.custom_identifiers else "")
        )

    for accepted in profile.accepted_identifiers:
        if match_identifier(identifier, accepted, profile.custom_identifiers):
            return MetricResult(
                metric_id="F1",
                principle="F",
                priority="essential",
                status="pass",
                description="Dataset has a globally unique persistent identifier",
                evidence=f"Identifier: {identifier} "
                    f"(matches accepted type: {accepted})"
            )

    for custom in profile.custom_identifiers:
        if match_identifier(identifier, custom.get("name", ""),
                            profile.custom_identifiers):
            return MetricResult(
                metric_id="F1",
                principle="F",
                priority="essential",
                status="pass",
                description="Dataset has a persistent identifier matching "
                    "a custom profile rule",
                evidence=f"Identifier: {identifier} "
                    f"(matches custom type: {custom.get('name')})"
            )

    detected_type = detect_identifier_type(identifier)
    return MetricResult(
        metric_id="F1",
        principle="F",
        priority="essential",
        status="fail",
        description="Identifier found but type not accepted by this profile",
        evidence=f"Identifier: {identifier} (detected type: {detected_type})",
        recommendation=f"Identifier type '{detected_type}' is not accepted. "
            f"This profile accepts: {', '.join(profile.accepted_identifiers)}"
            + (f" plus {len(profile.custom_identifiers)} custom type(s)"
               if profile.custom_identifiers else "")
            + ". Update the profile or use an accepted identifier type."
    )


def check_f2(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    core = metadata.core
    all_required = (profile.required_metadata_fields +
                    profile.custom_metadata_fields)

    # ── FAIR-Checker style: DCAT/schema.org property check ────────
    dcat_note = ""
    if profile.require_dcat_properties:
        dcat_props = [
            "dcat:", "@type", "schema:", "dcterms:identifier",
            "dcat:distribution", "schema:dataset", "schema:url",
        ]
        search = (
            str(metadata.core.dict()).lower() +
            str(metadata.custom).lower()
        )
        found_dcat = [p for p in dcat_props if p.lower() in search]
        if found_dcat:
            dcat_note = (
                f" DCAT/schema.org properties confirmed: "
                f"{', '.join(found_dcat)}."
            )
        else:
            dcat_note = (
                " Note: No DCAT or schema.org property signatures "
                "detected in the available metadata. The repository "
                "may not expose structured linked-data properties "
                "through its API."
            )

    if not all_required:
        return MetricResult(
            metric_id="F2",
            principle="F",
            priority="essential",
            status="pass" if not dcat_note or "confirmed" in dcat_note
                else "partial",
            description="No specific metadata fields required by this profile",
            evidence=(
                "No required fields configured."
                + dcat_note
            )
        )

    missing = []
    present = []
    for field in all_required:
        value = getattr(core, field, None)
        if value is None:
            value = metadata.custom.get(field)
        if value:
            present.append(field)
        else:
            missing.append(field)

    if not missing:
        return MetricResult(
            metric_id="F2",
            principle="F",
            priority="essential",
            status="pass",
            description="All required metadata fields are present",
            evidence=f"Present: {', '.join(present)}" + dcat_note
        )
    if present:
        custom_missing = [f for f in missing
                          if f in profile.custom_metadata_fields]
        note = ""
        if custom_missing:
            note = (f" Note: {', '.join(custom_missing)} are domain-specific "
                    f"fields that may not be exposed by the repository API.")
        return MetricResult(
            metric_id="F2",
            principle="F",
            priority="essential",
            status="partial",
            description="Some required metadata fields are missing",
            evidence=f"Present: {', '.join(present)} | "
                f"Missing: {', '.join(missing)}" + dcat_note,
            recommendation=f"Add missing fields: {', '.join(missing)}." + note
        )
    return MetricResult(
        metric_id="F2",
        principle="F",
        priority="essential",
        status="fail",
        description="All required metadata fields are missing",
        evidence=f"Missing: {', '.join(missing)}" + dcat_note,
        recommendation=f"No required fields found. "
            f"This profile requires: {', '.join(all_required)}"
    )


def check_f3(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    if metadata.core.identifier and metadata.core.access_url:
        return MetricResult(
            metric_id="F3",
            principle="F",
            priority="essential",
            status="pass",
            description="Metadata includes the identifier of the dataset",
            evidence=f"Identifier in metadata: {metadata.core.identifier}"
        )
    return MetricResult(
        metric_id="F3",
        principle="F",
        priority="essential",
        status="fail",
        description="Metadata does not include the dataset identifier",
        recommendation="Ensure metadata explicitly references the "
            "dataset identifier"
    )


def check_f4(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    if not profile.check_discoverability:
        return MetricResult(
            metric_id="F4",
            principle="F",
            priority="essential",
            status="pass",
            description="Discoverability check disabled for this profile",
            evidence="check_discoverability = false"
        )
    if metadata.core.access_url:
        return MetricResult(
            metric_id="F4",
            principle="F",
            priority="essential",
            status="pass",
            description="Metadata is retrievable via standard identifier",
            evidence=f"Access URL: {metadata.core.access_url}"
        )
    return MetricResult(
        metric_id="F4",
        principle="F",
        priority="essential",
        status="fail",
        description="No access URL found — metadata may not be discoverable",
        recommendation="Ensure dataset has a resolvable access URL"
    )


# ─── A Metrics ────────────────────────────────────────────────

def check_a1(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    """Evaluate A1 — Metadata Retrievability.

    When ``profile.check_access_level`` is True (F-UJI FsF-A1-01M style),
    the metric additionally requires that access level / access rights
    information is declared in the metadata.  Without it the result is
    downgraded to partial even when a valid access URL is present.
    """
    url = metadata.core.access_url
    url_ok = bool(url and (
        url.startswith("http://") or url.startswith("https://")
    ))

    # ── F-UJI style: access level / access rights declaration ────
    if profile.check_access_level:
        # Fields that carry access level info in typical repository APIs
        access_field_names = [
            "access_level", "access_rights", "accessrights",
            "accessLevel", "accessRights", "rights",
            "openaire_access", "access", "availability",
        ]
        # F-UJI behaviour: values that look like CC/open-source license strings
        # are explicitly ignored as access-rights evidence.  Only applies when
        # a1_license_fallback is False (i.e. F-UJI Equivalent mode).
        # Matches F-UJI debug message: "Access condition looks like license,
        # therefore the following is ignored".
        _cc_license_signals = [
            "creativecommons.org", "creative commons",
            "cc0", "cc-by", "cc by", "publicdomain",
        ]

        def _looks_like_license(val: str) -> bool:
            if profile.a1_license_fallback:
                return False          # FAIR-Checker mode: treat as valid
            vl = val.lower()
            return any(sig in vl for sig in _cc_license_signals)

        access_found = None
        for field in access_field_names:
            val = (metadata.custom.get(field)
                   or metadata.custom.get(field.lower()))
            if val and not _looks_like_license(str(val)):
                access_found = f"{field}: {val}"
                break

        # Broad fallback: scan every custom field value for known access terms.
        # This catches cases where the value is present under an unexpected key
        # (e.g. F-UJI detects "public" from Zenodo's schema.org conditionsOfAccess
        # which may land in a custom field with a different name).
        if not access_found:
            _access_terms = {
                "open", "public", "restricted", "closed", "embargoed",
                "open access", "openaccess",
                "info:eu-repo/semantics/openaccess",
                "info:eu-repo/semantics/restrictedaccess",
                "info:eu-repo/semantics/closedaccess",
            }
            for k, v in metadata.custom.items():
                if not isinstance(v, str) or not v:
                    continue
                if _looks_like_license(v):
                    continue          # skip license strings (F-UJI behaviour)
                vl = v.lower().strip()
                if vl in _access_terms or any(t in vl for t in _access_terms):
                    access_found = f"{k}: {v}"
                    break

        # License fallback (FAIR-Checker A12 style, opt-in via profile flag):
        # an open/permissive license is sufficient evidence that access rights
        # are declared.  Disabled for F-UJI Equivalent which requires an
        # explicit access_level / access_rights field.
        if (not access_found
                and profile.a1_license_fallback
                and metadata.core.license):
            _open_lic_terms = [
                "creativecommons.org", "cc-by", "cc0", "cc by",
                "public domain", "mit", "apache", "bsd", "open",
            ]
            lic_lower = metadata.core.license.lower()
            if any(t in lic_lower for t in _open_lic_terms):
                access_found = (
                    f"license: {metadata.core.license} "
                    f"(open license implies access rights are declared)"
                )

        # F-UJI: access level info must be present in metadata (FsF-A1-01M-1).
        if url_ok:
            if access_found:
                return MetricResult(
                    metric_id="A1",
                    principle="A",
                    priority="essential",
                    status="pass",
                    description=(
                        "Metadata is accessible via HTTP/HTTPS and "
                        "access conditions are declared"
                    ),
                    evidence=f"Access URL: {url} | {access_found}"
                )
            # No explicit access_level field → FAIL (matches F-UJI 0/1 score)
            return MetricResult(
                metric_id="A1",
                principle="A",
                priority="essential",
                status="fail",
                description=(
                    "Metadata is accessible via HTTP/HTTPS but "
                    "no explicit access level or access rights field found"
                ),
                evidence="access_level / access_rights field is absent or null",
                recommendation=(
                    "Add an explicit access_level or access_rights field to "
                    "metadata (e.g. access_level: open). "
                )
            )
        return MetricResult(
            metric_id="A1",
            principle="A",
            priority="essential",
            status="fail",
            description="No HTTP/HTTPS access URL found",
            recommendation="Provide an access URL using HTTP or HTTPS"
        )

    # ── Default: HTTP/HTTPS URL presence only ────────────────────
    if url_ok:
        return MetricResult(
            metric_id="A1",
            principle="A",
            priority="essential",
            status="pass",
            description="Metadata is accessible via HTTP/HTTPS",
            evidence=f"Access URL: {url}"
        )
    return MetricResult(
        metric_id="A1",
        principle="A",
        priority="essential",
        status="fail",
        description="No HTTP/HTTPS access URL found",
        recommendation="Provide an access URL using HTTP or HTTPS"
    )


def check_a1_1(metadata: NormalizedMetadata,
               profile: Profile) -> MetricResult:
    url = metadata.core.access_url
    if url and url.startswith("https://"):
        return MetricResult(
            metric_id="A1.1",
            principle="A",
            priority="essential",
            status="pass",
            description="Metadata uses open standard protocol (HTTPS)",
            evidence="Protocol: HTTPS"
        )
    if url and url.startswith("http://"):
        return MetricResult(
            metric_id="A1.1",
            principle="A",
            priority="essential",
            status="partial",
            description="Metadata uses HTTP instead of HTTPS",
            evidence="Protocol: HTTP (unencrypted)",
            recommendation="Use HTTPS instead of HTTP for secure access"
        )
    return MetricResult(
        metric_id="A1.1",
        principle="A",
        priority="essential",
        status="fail",
        description="No open standard protocol URL detected",
        recommendation="Use HTTPS to make metadata accessible"
    )


def check_a1_2(metadata: NormalizedMetadata,
               profile: Profile) -> MetricResult:
    license_val = metadata.core.license
    open_licenses = ["cc0", "cc-by", "cc by", "public domain",
                     "open", "mit", "apache", "bsd",
                     "creativecommons.org"]
    is_open = license_val and any(
        l in license_val.lower() for l in open_licenses
    )
    if is_open:
        return MetricResult(
            metric_id="A1.2",
            principle="A",
            priority="useful",
            status="pass",
            description="Dataset is openly licensed — no authentication required",
            evidence=f"Open license: {license_val}"
        )
    if metadata.core.access_url:
        return MetricResult(
            metric_id="A1.2",
            principle="A",
            priority="useful",
            status="partial",
            description="Access URL present but authentication requirements unclear",
            evidence=f"Access URL: {metadata.core.access_url}",
            recommendation="Specify access rights and authentication "
                "requirements in metadata if data is restricted"
        )
    return MetricResult(
        metric_id="A1.2",
        principle="A",
        priority="useful",
        status="fail",
        description="No access or license information found",
        recommendation="Add access rights information to metadata"
    )


def check_a2(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    if metadata.core.identifier and metadata.core.access_url:
        if metadata.core.title:
            return MetricResult(
                metric_id="A2",
                principle="A",
                priority="essential",
                status="pass",
                description="Metadata is accessible independently of the data",
                evidence=f"Rich metadata retrieved: "
                    f"'{metadata.core.title[:60]}'"
            )
        return MetricResult(
            metric_id="A2",
            principle="A",
            priority="essential",
            status="partial",
            description="Identifier resolves but metadata content is minimal",
            evidence="Identifier resolves but limited metadata retrieved",
            recommendation="Ensure rich metadata is stored and accessible "
                "independently of the data files"
        )
    return MetricResult(
        metric_id="A2",
        principle="A",
        priority="essential",
        status="fail",
        description="Cannot confirm metadata persists independently of data",
        recommendation="Ensure metadata remains accessible even if data "
            "is no longer available"
    )


# ─── I Metrics ────────────────────────────────────────────────

def check_i1(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    """Evaluate I1 — Knowledge Representation Language / File Format.

    Checking strategy is controlled by ``profile.i1_check_source``:
    - ``"metadata"``      – read format from the metadata API (default)
    - ``"landing_page"``  – detect format by requesting the access URL
                            (F-UJI style: inspects content-type + HTML)
    - ``"both"``          – combine both sources

    When ``profile.check_rdf_triples`` is True the function behaves in
    FAIR-Checker mode: it attempts RDF content negotiation on the access
    URL and passes if any RDF serialisation is returned, regardless of
    the ``accepted_formats`` list.
    """
    accepted = [f.lower() for f in profile.accepted_formats]
    formats_found: list = []
    evidence_parts: list = []

    # ── Metadata source ────────────────────────────────────────
    if profile.i1_check_source in ("metadata", "both"):
        meta_formats = [f.lower() for f in metadata.core.formats]
        if meta_formats:
            formats_found.extend(meta_formats)
            evidence_parts.append(
                f"Metadata formats: {', '.join(meta_formats)}"
            )

    # ── Landing page source ────────────────────────────────────
    needs_lp = (
        profile.i1_check_source in ("landing_page", "both")
        or profile.check_rdf_triples
    )
    lp_formats: list = []
    lp_note = ""
    if needs_lp:
        url = metadata.core.access_url
        if url:
            lp_formats, lp_note = fetch_landing_page_formats(url)
            for f in lp_formats:
                if f not in formats_found:
                    formats_found.append(f)
            if lp_formats:
                evidence_parts.append(
                    f"Landing page formats: {', '.join(lp_formats)} "
                    f"({lp_note})"
                )
            else:
                evidence_parts.append(
                    f"Landing page: no format detected ({lp_note})"
                )
        else:
            evidence_parts.append(
                "Landing page: skipped — no access URL in metadata"
            )

    evidence_str = " | ".join(evidence_parts) if evidence_parts \
        else "No format information found"

    # ── FAIR-Checker mode: pass on any RDF serialisation ──────
    if profile.check_rdf_triples:
        rdf_types = {"turtle", "rdf", "json-ld", "rdf/xml"}
        rdf_found = [f for f in formats_found
                     if any(r in f for r in rdf_types)]
        if rdf_found:
            return MetricResult(
                metric_id="I1",
                principle="I",
                priority="important",
                status="pass",
                description="Linked data representation detected via "
                    "content negotiation on the landing page",
                evidence=(
                    f"RDF format: {', '.join(rdf_found)} | {evidence_str}"
                )
            )
        return MetricResult(
            metric_id="I1",
            principle="I",
            priority="important",
            status="fail",
            description="No linked data representation (RDF/JSON-LD) "
                "detected on landing page",
            evidence=evidence_str,
            recommendation=(
                "Ensure the landing page supports content negotiation "
                "for RDF serialisations (Turtle, JSON-LD, or RDF/XML). "
                f"Note: detection depends on landing page accessibility. "
                f"{lp_note}"
            )
        )

    # ── Standard format check ──────────────────────────────────
    matched = [
        f for f in formats_found
        if any(a in f or f in a for a in accepted)
    ]

    if matched:
        source_label = {
            "metadata": "from metadata",
            "landing_page": "from landing page",
            "both": "from metadata and/or landing page",
        }.get(profile.i1_check_source, "")
        return MetricResult(
            metric_id="I1",
            principle="I",
            priority="important",
            status="pass",
            description=(
                f"Data is in an accepted machine-readable format"
                f"{' (' + source_label + ')' if source_label else ''}"
            ),
            evidence=evidence_str
        )

    if formats_found:
        return MetricResult(
            metric_id="I1",
            principle="I",
            priority="important",
            status="partial",
            description="Format detected but not in accepted list",
            evidence=evidence_str,
            recommendation=(
                f"Format(s) '{', '.join(formats_found)}' not accepted. "
                f"This profile requires one of: "
                f"{', '.join(profile.accepted_formats)}"
            )
        )

    return MetricResult(
        metric_id="I1",
        principle="I",
        priority="important",
        status="fail",
        description="No file format information found",
        evidence=evidence_str,
        recommendation=(
            f"Specify the data format. "
            f"This profile accepts: {', '.join(profile.accepted_formats)}"
            + (
                " Note: this profile checks the landing page — "
                "ensure the access URL is reachable."
                if profile.i1_check_source != "metadata" else ""
            )
        )
    )


def check_i2(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    """Evaluate I2 — Use of FAIR Vocabularies.

    When ``profile.i2_namespace_check`` is True (F-UJI FsF-I2-01M style),
    detection is based on scanning metadata for registered ontology namespace
    URIs (e.g. http://schema.org/, http://www.w3.org/ns/dcat) rather than
    keyword matching.  This mirrors how F-UJI identifies semantic resources.

    When the flag is False (default), the original keyword-matching logic
    is used, which is more lenient.
    """
    search_text = (
        str(metadata.core.dict()).lower() + str(metadata.custom).lower()
    )

    # ── F-UJI style: namespace URI detection ──────────────────────
    if profile.i2_namespace_check:
        found_ns: list = []
        for vocab_name, uris in KNOWN_VOCAB_NAMESPACES.items():
            if any(uri.lower() in search_text for uri in uris):
                found_ns.append(vocab_name)

        if found_ns:
            return MetricResult(
                metric_id="I2",
                principle="I",
                priority="important",
                status="pass",
                description=(
                    "Metadata uses registered semantic vocabulary "
                    "namespaces"
                ),
                evidence=(
                    f"Registered namespaces detected: "
                    f"{', '.join(found_ns)}"
                )
            )
        return MetricResult(
            metric_id="I2",
            principle="I",
            priority="important",
            status="fail",
            description=(
                "No registered semantic vocabulary namespace URIs "
                "detected in metadata"
            ),
            evidence=(
                "Namespace URI scan found no matches against known "
                "registered vocabularies. Note: this check requires "
                "namespace URIs to be present in the raw metadata "
                "response — many REST APIs serialize vocabulary "
                "references as plain text rather than URIs."
            ),
            recommendation=(
                "Ensure metadata includes explicit vocabulary namespace "
                "URIs (e.g. http://schema.org/, "
                "http://www.w3.org/ns/dcat). "
                "Use linked-data serializations (JSON-LD, RDF/XML, "
                "Turtle) that embed namespace declarations."
            )
        )

    # ── Default: keyword-based detection ──────────────────────────
    all_vocabs = []
    if profile.required_vocabulary:
        all_vocabs.append({
            "name": profile.required_vocabulary,
            "keywords": [profile.required_vocabulary.lower()],
            "description": f"Required vocabulary: {profile.required_vocabulary}"
        })
    all_vocabs.extend(profile.custom_vocabularies)

    if not all_vocabs:
        known = {
            "schema.org": ["schema.org", '"@context"', "schema:"],
            "Dublin Core": ["dcterms:", "dc.title", "dublin core",
                            "dcterms", "dc:"],
            "DCAT": ["dcat:", "dcat."],
            "SKOS": ["skos:", "skos."]
        }
        found = [name for name, kws in known.items()
                 if any(kw.lower() in search_text for kw in kws)]
        if found:
            return MetricResult(
                metric_id="I2",
                principle="I",
                priority="important",
                status="pass",
                description="Metadata uses standard semantic vocabulary",
                evidence=f"Vocabulary references found: {', '.join(found)}"
            )
        return MetricResult(
            metric_id="I2",
            principle="I",
            priority="important",
            status="partial",
            description="No vocabulary required but none detected in metadata",
            evidence="No standard vocabulary references found",
            recommendation="Consider using schema.org, DCAT, or Dublin Core "
                "to improve interoperability"
        )

    passed = []
    failed = []
    for vocab in all_vocabs:
        if check_vocabulary(metadata, vocab):
            passed.append(vocab["name"])
        else:
            failed.append(vocab["name"])

    if not failed:
        return MetricResult(
            metric_id="I2",
            principle="I",
            priority="important",
            status="pass",
            description="Metadata uses all required vocabularies",
            evidence=f"Vocabularies confirmed: {', '.join(passed)}"
        )
    if passed:
        return MetricResult(
            metric_id="I2",
            principle="I",
            priority="important",
            status="partial",
            description="Some required vocabularies not detected",
            evidence=f"Found: {', '.join(passed)} | "
                f"Not detected: {', '.join(failed)}. "
                f"Note: detection depends on repository API response.",
            recommendation=f"Add references to: {', '.join(failed)}. "
                f"Ensure metadata uses these vocabularies and that "
                f"the repository exposes them through its API."
        )
    return MetricResult(
        metric_id="I2",
        principle="I",
        priority="important",
        status="fail",
        description="Required vocabularies not detected in metadata",
        evidence=f"Required but not found: {', '.join(failed)}. "
            f"Note: vocabulary detection depends on the repository "
            f"exposing vocabulary references in their API response.",
        recommendation=f"This profile requires: {', '.join(failed)}. "
            f"Ensure metadata uses these controlled vocabularies and "
            f"that your repository exposes vocabulary references "
            f"through its metadata API."
    )


def check_i3(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    """Evaluate I3 — Qualified References to Other Data.

    When ``profile.min_url_authorities > 0`` (FAIR-Checker style),
    the check counts how many distinct URL hostname authorities appear
    anywhere in the metadata.  This mirrors FAIR-Checker's requirement
    that metadata link to multiple external resources.

    When ``min_url_authorities`` is 0 (default), the check falls back
    to keyword search for qualified relation terms.
    """
    # ── FAIR-Checker style: URL authority count ────────────────
    if profile.min_url_authorities > 0:
        search = str(metadata.core.dict()) + str(metadata.custom)
        # Extract all hostnames from URLs in the metadata
        raw_urls = re.findall(r"https?://([^/\s\"\'>\]]+)", search)
        # Normalise: strip common suffixes, lower-case
        domains = {
            re.sub(r":\d+$", "", h).lower()
            for h in raw_urls
            if h  # exclude empty
        }
        n = len(domains)
        req = profile.min_url_authorities
        if n >= req:
            sample = sorted(domains)[:5]
            return MetricResult(
                metric_id="I3",
                principle="I",
                priority="important",
                status="pass",
                description=(
                    f"Metadata references {n} distinct URL "
                    f"authorit{'y' if n == 1 else 'ies'}, "
                    f"meeting the minimum of {req}"
                ),
                evidence=(
                    f"URL authorities ({n}): "
                    f"{', '.join(sample)}"
                    f"{'...' if n > 5 else ''}"
                )
            )
        return MetricResult(
            metric_id="I3",
            principle="I",
            priority="important",
            status="partial" if n > 0 else "fail",
            description=(
                f"Insufficient URL authorities in metadata "
                f"({n} found, {req} required)"
            ),
            evidence=(
                f"URL authorities found: "
                f"{', '.join(sorted(domains)) if domains else 'none'}"
            ),
            recommendation=(
                f"Add links to related datasets or resources from "
                f"additional domains. "
                f"This profile requires at least {req} distinct URL "
                f"authorities across all metadata fields."
            )
        )

    # ── Default: qualified-relation keyword search ─────────────
    custom_str = str(metadata.custom).lower()
    core_str = str(metadata.core.dict()).lower()
    search = custom_str + core_str

    reference_keywords = [
        "related", "references", "citation", "ispartof",
        "isderivedfrom", "iscitedby", "isversionof",
        "relatedidentifier", "relation", "conformsto",
        "dcterms:references", "dcterms:relation"
    ]
    found = [kw for kw in reference_keywords if kw in search]

    if found:
        return MetricResult(
            metric_id="I3",
            principle="I",
            priority="important",
            status="pass",
            description="Metadata includes qualified references to "
                "related resources",
            evidence=f"Reference fields detected: {', '.join(found)}"
        )

    if profile.require_related_resources:
        return MetricResult(
            metric_id="I3",
            principle="I",
            priority="important",
            status="fail",
            description="No qualified references found — required by "
                "this profile",
            evidence="No relatedIdentifiers or citation fields detected",
            recommendation="Add qualified references to related datasets, "
                "publications, or derived resources"
        )

    return MetricResult(
        metric_id="I3",
        principle="I",
        priority="important",
        status="partial",
        description="No qualified references found in metadata",
        evidence="No relatedIdentifiers or citation links detected",
        recommendation="Consider adding references to related datasets "
            "or publications to improve interoperability"
    )


# ─── R Metrics ────────────────────────────────────────────────

def check_r1(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    core = metadata.core
    all_fields = (profile.required_metadata_fields +
                  profile.custom_metadata_fields)
    if not all_fields:
        all_fields = ["title", "description", "creator", "license"]

    present = []
    missing = []
    for field in all_fields:
        val = getattr(core, field, None) or metadata.custom.get(field)
        if val:
            present.append(field)
        else:
            missing.append(field)

    # ── FsF-R1-01M-3 (optional): Measured variables check ─────────
    measured_ok = True
    measured_evidence = ""
    if profile.r1_check_measured_variables:
        variable_fields = [
            "variableMeasured", "variables", "measured_variables",
            "variable_measured", "hasPart", "observationType",
            "observation_type", "parameters",
        ]
        measured_val = None
        for vf in variable_fields:
            measured_val = (getattr(core, vf, None)
                            or metadata.custom.get(vf)
                            or metadata.custom.get(vf.lower()))
            if measured_val:
                measured_evidence = f"Measured variables: {vf}"
                break
        if not measured_val:
            measured_ok = False
            measured_evidence = (
                "No measured variables / observation types found"
            )

    # ── FsF-R1-01M-1 (optional): Resource type check ──────────────
    resource_type_ok = True
    resource_type_evidence = ""
    if profile.r1_check_resource_type:
        rt_fields = [
            "resource_type", "object_type", "resourceType",
            "resourceTypeGeneral", "type",
        ]
        rt_val = None
        for rf in rt_fields:
            rt_val = (getattr(core, rf, None)
                      or metadata.custom.get(rf)
                      or metadata.custom.get(rf.lower()))
            if rt_val:
                resource_type_evidence = f"Resource type: {rt_val}"
                break
        if not rt_val:
            resource_type_ok = False
            resource_type_evidence = (
                "No resource / object type declared in metadata "
                "(e.g. resourceTypeGeneral: Dataset)"
            )

    # ── FsF-R1-01M-2 (optional): File format / type / size info check ──
    # F-UJI passes this test when EITHER file type OR file size is present.
    file_type_ok = True
    file_type_evidence = ""
    if profile.r1_check_file_type_info:
        fmt_list = list(core.formats or [])
        size_val = None

        if not fmt_list:
            # Check custom fields for format / MIME type
            for ff in ["format", "encodingFormat", "mediaType",
                       "file_format", "fileFormat"]:
                v = metadata.custom.get(ff) or metadata.custom.get(ff.lower())
                if v:
                    fmt_list = [str(v)]
                    break

        # Also look for file size — F-UJI accepts size alone (FsF-R1-01M-2)
        for sf in ["file_size", "fileSize", "contentSize", "size", "sizes"]:
            sv = metadata.custom.get(sf) or metadata.custom.get(sf.lower())
            if sv:
                size_val = str(sv)
                break

        if fmt_list or size_val:
            parts = []
            if fmt_list:
                parts.append(f"format: {', '.join(fmt_list[:5])}")
            if size_val:
                parts.append(f"size: {size_val}")
            file_type_evidence = "File info — " + " | ".join(parts)
        else:
            file_type_ok = False
            file_type_evidence = (
                "No file format, MIME type, or file size information found in metadata"
            )

    # ── Determine final status ────────────────────────────────────
    base_status = "pass" if not missing else ("partial" if present else "fail")

    # Collect sub-check failures to downgrade status and show evidence
    sub_fails = []
    ev_parts = []

    if base_status == "pass":
        ev_parts.append(f"Fields: {', '.join(present)}")
    elif present:
        ev_parts.append(f"Present: {', '.join(present)} | Missing: {', '.join(missing)}")
    else:
        ev_parts.append(f"Missing: {', '.join(missing)}")

    if profile.r1_check_resource_type:
        ev_parts.append(resource_type_evidence)
        if not resource_type_ok:
            sub_fails.append("resource type not declared")
    if profile.r1_check_file_type_info:
        ev_parts.append(file_type_evidence)
        if not file_type_ok:
            sub_fails.append("file format info absent")
    if profile.r1_check_measured_variables:
        ev_parts.append(measured_evidence)
        if not measured_ok:
            sub_fails.append("measured variables missing")

    if sub_fails and base_status == "pass":
        base_status = "partial"

    combined_ev = " | ".join(e for e in ev_parts if e)

    if base_status == "pass":
        return MetricResult(
            metric_id="R1",
            principle="R",
            priority="essential",
            status="pass",
            description="Metadata contains sufficient information for reuse",
            evidence=combined_ev
        )
    if base_status == "partial":
        desc_parts = []
        if missing:
            desc_parts.append(f"missing fields: {', '.join(missing)}")
        desc_parts.extend(sub_fails)
        return MetricResult(
            metric_id="R1",
            principle="R",
            priority="essential",
            status="partial",
            description="Metadata partially satisfies reuse requirements: "
                        + "; ".join(desc_parts),
            evidence=combined_ev,
            recommendation=(
                (f"Add missing fields: {', '.join(missing)}. " if missing else "")
                + (f"Declare resource type (e.g. resourceTypeGeneral: Dataset). "
                   if not resource_type_ok else "")
                + ("Add file format / size information to metadata. "
                   if not file_type_ok else "")
            ).strip()
        )
    return MetricResult(
        metric_id="R1",
        principle="R",
        priority="essential",
        status="fail",
        description="Metadata missing fields needed for reuse",
        evidence=combined_ev,
        recommendation=f"Add required fields: {', '.join(all_fields)}"
    )


def check_r1_1(metadata: NormalizedMetadata,
               profile: Profile) -> MetricResult:
    """Evaluate R1.1 — Data Usage License.

    Three strictness modes controlled by profile flags:

    1. ``r1_1_spdx_check = True``  (F-UJI style)
       Validates the license value against the SPDX recognised list.
       Accepts both SPDX identifiers (e.g. 'CC-BY-4.0') and URIs from
       known registries (creativecommons.org, spdx.org, opensource.org).

    2. ``r1_1_require_license_uri = True`` (FAIR-Checker style)
       Requires the license value to be a URI (starts with http/https).
       Text-only license values ('CC-BY 4.0') produce a partial result.

    3. Neither flag set (default)
       Passes on any machine-readable license, optionally matched
       against ``accepted_licenses``.
    """
    license_val = metadata.core.license
    accepted = [l.lower() for l in profile.accepted_licenses]
    required = profile.required_license

    if not license_val:
        return MetricResult(
            metric_id="R1.1",
            principle="R",
            priority="essential",
            status="fail",
            description="No license found in metadata",
            recommendation="Add a machine-readable license"
                + (f" — this profile requires: {required}"
                   if required else
                   (f". Accepted: {', '.join(profile.accepted_licenses)}"
                    if profile.accepted_licenses else ""))
        )

    license_lower = license_val.lower()

    # ── F-UJI style: SPDX validation ──────────────────────────
    if profile.r1_1_spdx_check:
        if is_spdx_license(license_val):
            return MetricResult(
                metric_id="R1.1",
                principle="R",
                priority="essential",
                status="pass",
                description="Dataset has a machine-readable, "
                    "SPDX-recognised license",
                evidence=f"SPDX-recognised license: {license_val}"
            )
        return MetricResult(
            metric_id="R1.1",
            principle="R",
            priority="essential",
            status="partial",
            description="License found but not recognised as an SPDX "
                "standard identifier or URI",
            evidence=f"License: {license_val}",
            recommendation=(
                "Use an SPDX licence identifier or a canonical URI "
                "(e.g. 'CC-BY-4.0' or "
                "'https://creativecommons.org/licenses/by/4.0/'). "
                "See https://spdx.org/licenses/ for the full list."
            )
        )

    # ── FAIR-Checker style: require URI ────────────────────────
    if profile.r1_1_require_license_uri:
        if is_license_uri(license_val):
            return MetricResult(
                metric_id="R1.1",
                principle="R",
                priority="essential",
                status="pass",
                description="Dataset has a machine-readable license URI",
                evidence=f"License URI: {license_val}"
            )
        return MetricResult(
            metric_id="R1.1",
            principle="R",
            priority="essential",
            status="partial",
            description="License text found but not as a machine-readable URI",
            evidence=f"License (text only): {license_val}",
            recommendation=(
                "Provide the license as a URI so it is machine-readable "
                "(e.g. https://creativecommons.org/licenses/by/4.0/). "
                "A plain text label is not sufficient for this profile."
            )
        )

    # ── Default: accepted-list or any-license check ────────────
    license_aliases = {
        "cc-by": ["cc-by", "creativecommons.org/licenses/by",
                  "cc by", "attribution"],
        "cc0": ["cc0", "creativecommons.org/publicdomain/zero",
                "public domain", "cc zero"],
        "cc-by-sa": ["cc-by-sa", "creativecommons.org/licenses/by-sa"],
        "cc-by-nc": ["cc-by-nc", "creativecommons.org/licenses/by-nc"],
        "mit": ["mit license", "opensource.org/licenses/mit"],
        "apache": ["apache", "opensource.org/licenses/apache"],
        "gpl": ["gpl", "gnu general public"],
        "bsd": ["bsd", "opensource.org/licenses/bsd"],
    }

    def matches_license(accepted_name: str, license_text: str) -> bool:
        name = accepted_name.lower()
        aliases = license_aliases.get(name, [name])
        return any(alias in license_text for alias in aliases)

    if required and not matches_license(required, license_lower):
        return MetricResult(
            metric_id="R1.1",
            principle="R",
            priority="essential",
            status="partial",
            description="License found but does not match required license",
            evidence=f"Current license: {license_val}",
            recommendation=f"License detected but this profile "
                f"requires: {required}"
        )

    if accepted:
        if any(matches_license(a, license_lower) for a in accepted):
            return MetricResult(
                metric_id="R1.1",
                principle="R",
                priority="essential",
                status="pass",
                description="Dataset has a valid machine-readable license",
                evidence=f"License: {license_val}"
            )
        return MetricResult(
            metric_id="R1.1",
            principle="R",
            priority="essential",
            status="partial",
            description="License found but not in accepted list",
            evidence=f"Current license: {license_val}",
            recommendation=f"License not in accepted list. "
                f"Accepted: {', '.join(profile.accepted_licenses)}"
        )

    return MetricResult(
        metric_id="R1.1",
        principle="R",
        priority="essential",
        status="pass",
        description="Dataset has a machine-readable license",
        evidence=f"License: {license_val}"
    )


def check_r1_2(metadata: NormalizedMetadata,
               profile: Profile) -> MetricResult:
    """Evaluate R1.2 — Data Provenance.

    When ``profile.r1_2_require_prov_ontology`` is True (F-UJI
    FsF-R1.2-01M-2 style), a full pass additionally requires that at
    least one formal provenance ontology URI (PROV-O or PAV) is present
    anywhere in the metadata.  Without it the result is downgraded to
    partial even when all named provenance fields are present.
    """
    core = metadata.core
    required_fields = profile.required_provenance_fields
    field_map = {
        "creator":        core.creator,
        "provenance_date": core.provenance_date,
        "description":    core.description,
        "title":          core.title,
    }

    present = []
    missing = []
    for field in required_fields:
        val = field_map.get(field) or metadata.custom.get(field)
        if val:
            present.append(field)
        else:
            missing.append(field)

    # ── Check for formal PROV/PAV ontology (F-UJI test 2) ────────
    prov_note = ""
    if profile.r1_2_require_prov_ontology:
        search = str(metadata.core.dict()) + str(metadata.custom)
        prov_found = [uri for uri in PROV_ONTOLOGY_URIS if uri in search]
        if prov_found:
            prov_note = (
                f" Formal provenance ontology detected: "
                f"{prov_found[0]}"
            )
        else:
            prov_note = (
                " Note: no formal provenance ontology URI (PROV-O or PAV) "
                "found in metadata — required for a full pass by this profile."
            )

    fields_ok = not missing

    if fields_ok:
        if profile.r1_2_require_prov_ontology and not prov_found:
            return MetricResult(
                metric_id="R1.2",
                principle="R",
                priority="important",
                status="partial",
                description=(
                    "Provenance fields present but no formal PROV/PAV "
                    "ontology URI found in metadata"
                ),
                evidence=(
                    f"Provenance fields: {', '.join(present)}" + prov_note
                ),
                recommendation=(
                    "Include a formal provenance ontology reference "
                    "(PROV-O: http://www.w3.org/ns/prov or "
                    "PAV: http://purl.org/pav) in metadata. "
                    "Repositories using JSON-LD or RDF serialisations "
                    "typically embed these automatically."
                )
            )
        return MetricResult(
            metric_id="R1.2",
            principle="R",
            priority="important",
            status="pass",
            description="All required provenance information is present",
            evidence=f"Provenance fields: {', '.join(present)}" + prov_note
        )
    if present:
        return MetricResult(
            metric_id="R1.2",
            principle="R",
            priority="important",
            status="partial",
            description="Incomplete provenance information",
            evidence=(
                f"Present: {', '.join(present)} | "
                f"Missing: {', '.join(missing)}" + prov_note
            ),
            recommendation=f"Add missing provenance: {', '.join(missing)}"
        )
    return MetricResult(
        metric_id="R1.2",
        principle="R",
        priority="important",
        status="fail",
        description="No provenance information found",
        evidence=f"Missing: {', '.join(missing)}",
        recommendation=f"Add provenance fields: {', '.join(required_fields)}"
    )


def check_r1_3(metadata: NormalizedMetadata,
               profile: Profile) -> MetricResult:
    """Evaluate R1.3 — Meets Domain-Relevant Community Standards.

    Two modes controlled by ``profile.required_community_standards``:

    **Standards mode** (list is non-empty):
        Scans the raw metadata text for each required standard's namespace /
        URI patterns (see COMMUNITY_STANDARDS_PATTERNS).
        - All required standards detected  → pass
        - Some detected                    → partial
        - None detected                    → fail

    **Format mode** (list is empty — default):
        Falls back to checking whether data formats match the profile's
        ``accepted_formats`` list (legacy behaviour, same source strategy
        as I1: metadata API, landing page, or both).
    """
    standard = profile.community_standard

    # ── Standards mode ────────────────────────────────────────────
    if profile.required_community_standards:
        # Build text corpus from API metadata
        raw_text = json.dumps(metadata.custom).lower()
        raw_text += json.dumps({
            "title": metadata.core.title,
            "description": metadata.core.description,
            "formats": metadata.core.formats,
        }).lower()

        # First pass: scan API metadata
        found: list = []
        not_found: list = []
        for std_name in profile.required_community_standards:
            key = std_name.lower().strip()
            patterns = COMMUNITY_STANDARDS_PATTERNS.get(key, [key])
            if any(p.lower() in raw_text for p in patterns):
                found.append(std_name)
            else:
                not_found.append(std_name)

        # Second pass: scan landing-page HTML for standards not yet found in
        # API metadata.  Landing pages typically embed schema.org JSON-LD
        # (@context: "https://schema.org") and RDFa that API responses omit.
        if not_found:
            url = metadata.core.access_url
            if url:
                try:
                    import requests as _req
                    lp = _req.get(
                        url,
                        headers={"User-Agent": "ProFAIR/1.0"},
                        timeout=8,
                    )
                    if "text/html" in lp.headers.get("content-type", "").lower():
                        lp_text = lp.text.lower()
                        still_missing: list = []
                        for std_name in not_found:
                            key = std_name.lower().strip()
                            patterns = COMMUNITY_STANDARDS_PATTERNS.get(key, [key])
                            if any(p.lower() in lp_text for p in patterns):
                                found.append(std_name)
                            else:
                                still_missing.append(std_name)
                        not_found = still_missing
                except Exception:
                    pass  # network error — rely on API-metadata scan only

        # "any found → pass" matches both F-UJI (FsF-R1.3-01M-3: "any of
        # potential values") and FAIR-Checker (pass if schema.org detected).
        if found:
            extra = (
                f" | Not detected: {', '.join(not_found)}"
                if not_found else ""
            )
            return MetricResult(
                metric_id="R1.3",
                principle="R",
                priority="essential",
                status="pass",
                description="Community metadata standard(s) detected in metadata",
                evidence=f"Found: {', '.join(found)}{extra}"
            )
        return MetricResult(
            metric_id="R1.3",
            principle="R",
            priority="essential",
            status="fail",
            description="No required community standards detected in metadata",
            evidence=f"Required: {', '.join(profile.required_community_standards)}",
            recommendation=(
                "Ensure metadata includes namespace URIs or vocabulary terms "
                f"for: {', '.join(profile.required_community_standards)}"
            )
        )

    # ── Format mode (default) ─────────────────────────────────────
    accepted = [f.lower() for f in profile.accepted_formats]
    formats_found: list = []

    if profile.i1_check_source in ("metadata", "both"):
        meta_formats = [f.lower() for f in metadata.core.formats]
        formats_found.extend(meta_formats)

    if profile.i1_check_source in ("landing_page", "both"):
        url = metadata.core.access_url
        if url:
            lp_formats, _ = fetch_landing_page_formats(url)
            for f in lp_formats:
                if f not in formats_found:
                    formats_found.append(f)

    matched = [
        f for f in formats_found
        if any(a in f or f in a for a in accepted)
    ]

    if matched:
        return MetricResult(
            metric_id="R1.3",
            principle="R",
            priority="essential",
            status="pass",
            description="Data follows community standards"
                + (f" ({standard})" if standard else ""),
            evidence=f"Standard format detected: {', '.join(matched)}"
        )
    if formats_found:
        return MetricResult(
            metric_id="R1.3",
            principle="R",
            priority="essential",
            status="fail",
            description="Data format does not match community standards",
            evidence=f"Current format: {', '.join(formats_found)}",
            recommendation=f"Format '{', '.join(formats_found)}' not accepted. "
                f"This profile requires: {', '.join(profile.accepted_formats)}"
                + (f" ({standard} standard)" if standard else "")
        )
    return MetricResult(
        metric_id="R1.3",
        principle="R",
        priority="essential",
        status="fail",
        description="No format metadata to verify community standards",
        recommendation=f"Specify data format. "
            f"This profile requires: {', '.join(profile.accepted_formats)}"
    )


# ─── Scoring ──────────────────────────────────────────────────

METRIC_WEIGHTS = {
    "F1": 1.0,
    "F2": 1.0,
    "F3": 1.0,
    "F4": 1.0,
    "A1": 1.0,
    "A1.1": 1.0,
    "A1.2": 0.5,
    "A2": 1.0,
    "I1": 0.75,
    "I2": 0.75,
    "I3": 0.5,
    "R1": 1.0,
    "R1.1": 1.0,
    "R1.2": 0.75,
    "R1.3": 1.0,
}


def calculate_score(results: list, principle: str) -> float:
    principle_results = [r for r in results if r.principle == principle]
    if not principle_results:
        return 0.0
    total_weight = 0.0
    earned = 0.0
    for r in principle_results:
        weight = METRIC_WEIGHTS.get(r.metric_id, 1.0)
        total_weight += weight
        if r.status == "pass":
            earned += weight
        elif r.status == "partial":
            earned += weight * 0.5
    return round((earned / total_weight) * 100, 1)


def run_assessment(metadata: NormalizedMetadata,
                   profile_name: str = "generic",
                   vocab_fairness=None) -> AssessmentReport:
    # vocab_fairness is accepted for backward-compatibility with main.py callers
    # that call assess_vocab_fairness() externally. Vocabulary evaluation is now
    # handled internally by check_i2() using the profile's min_vocab_fairness_level.
    profile = load_profile(profile_name)

    results = [
        check_f1(metadata, profile),
        check_f2(metadata, profile),
        check_f3(metadata, profile),
        check_f4(metadata, profile),
        check_a1(metadata, profile),
        check_a1_1(metadata, profile),
        check_a1_2(metadata, profile),
        check_a2(metadata, profile),
        check_i1(metadata, profile),
        check_i2(metadata, profile),
        check_i3(metadata, profile),
        check_r1(metadata, profile),
        check_r1_1(metadata, profile),
        check_r1_2(metadata, profile),
        check_r1_3(metadata, profile),
    ]

    f_score = calculate_score(results, "F")
    a_score = calculate_score(results, "A")
    i_score = calculate_score(results, "I")
    r_score = calculate_score(results, "R")
    overall = round((f_score + a_score + i_score + r_score) / 4, 1)
    maturity, maturity_desc = get_maturity(overall)

    return AssessmentReport(
        doi=metadata.raw_identifier,
        profile_name=profile.name,
        overall_score=overall,
        f_score=f_score,
        a_score=a_score,
        i_score=i_score,
        r_score=r_score,
        maturity_level=maturity,
        maturity_description=maturity_desc,
        results=results
    )
