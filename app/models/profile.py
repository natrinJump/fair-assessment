from pydantic import BaseModel
from typing import Optional


class CustomIdentifier(BaseModel):
    name: str
    match_type: str  # "starts_with", "contains", "regex"
    value: str
    description: Optional[str] = None


class CustomVocabulary(BaseModel):
    name: str
    check_url: Optional[str] = None
    keywords: list[str] = []
    description: Optional[str] = None


class Profile(BaseModel):
    name: str
    domain: str

    # F1 — identifier configuration
    accepted_identifiers: list[str] = []
    custom_identifiers: list[dict] = []

    # F2 — metadata fields
    required_metadata_fields: list[str] = []
    custom_metadata_fields: list[str] = []

    # F2 — FAIR-Checker style: check for DCAT/schema.org properties
    # When True, evaluator checks for dcat:, schema:, dcterms: signatures
    # in normalised metadata in addition to named field checks.
    require_dcat_properties: bool = False

    # A1 — F-UJI style: require explicit access level/rights declaration
    # (FsF-A1-01M: checks for access_level / access_rights in metadata)
    check_access_level: bool = False

    # A1 — FAIR-Checker style: accept an open license as evidence that access
    # rights are declared (A12 passes when CC-BY/CC0/etc. license is present).
    # Keep False for F-UJI Equivalent (strict field requirement); True for
    # FAIR-Checker Equivalent (more lenient).
    a1_license_fallback: bool = False

    # F4 — discoverability
    check_discoverability: bool = True

    # I1 — formats
    accepted_formats: list[str] = []

    # I1 — where to detect file format
    #   "metadata"     — read formats from the metadata API response (default)
    #   "landing_page" — detect format via HTTP request to the access URL
    #                    (F-UJI style: follows DOI, inspects content-type + HTML)
    #   "both"         — try metadata first, fall back to landing page
    i1_check_source: str = "metadata"

    # I1 — FAIR-Checker style: pass if RDF/JSON-LD is served via content
    # negotiation on the landing page (regardless of accepted_formats list)
    check_rdf_triples: bool = False

    # I2 — vocabularies
    required_vocabulary: Optional[str] = None
    custom_vocabularies: list[dict] = []
    min_vocab_fairness_level: str = "none"

    # I2 — F-UJI style: detect vocabularies by registered namespace URI
    # (FsF-I2-01M: semantic resource detection by namespace, not keyword)
    i2_namespace_check: bool = False

    # I2 — vocabularies to exclude from the namespace scan result
    # (e.g. F-UJI excludes schema.org, RDF, Dublin Core as "default namespaces")
    # Only applied when i2_namespace_check is True.
    excluded_vocabularies: list = []

    # I3 — qualified references
    require_related_resources: bool = False

    # I3 — FAIR-Checker style: require at least N distinct URL authorities
    # in metadata (0 = disabled, 3 = FAIR-Checker default)
    min_url_authorities: int = 0

    # R1.1 — licenses
    accepted_licenses: list[str] = []
    required_license: Optional[str] = None

    # R1.1 — F-UJI style: validate license against SPDX recognised list
    r1_1_spdx_check: bool = False

    # R1.1 — FAIR-Checker style: require license value to be a URI
    r1_1_require_license_uri: bool = False

    # R1.2 — provenance fields
    required_provenance_fields: list[str] = ["creator", "provenance_date"]

    # R1.2 — require formal PROV/PAV ontology URI in metadata
    r1_2_require_prov_ontology: bool = False

    # R1 — require measured variables / observation types in metadata
    # When True: checks for variableMeasured, variables, measured_variables,
    # hasPart fields; missing them downgrades the result to partial.
    r1_check_measured_variables: bool = False

    # R1 — FsF-R1-01M-1: require resource/object type in metadata
    # When True: checks that resource_type / object_type / @type is declared
    # (e.g. "Dataset"). Missing → partial.
    r1_check_resource_type: bool = False

    # R1 — FsF-R1-01M-2: require file format / type information in metadata
    # When True: checks that at least one file format or MIME type is listed
    # in metadata.core.formats or a known format field. Missing → partial.
    r1_check_file_type_info: bool = False

    # R1.3 — community standards
    # Single legacy string (kept for backward compat)
    community_standard: Optional[str] = None
    # List of required community standards to detect in metadata.
    # When non-empty, R1.3 switches from format-matching to namespace/URI
    # detection: all found → pass, some found → partial, none found → fail.
    # Standard names are matched case-insensitively against a built-in
    # namespace pattern table (Schema.org, DataCite, DDI, Darwin Core, etc.).
    required_community_standards: list[str] = []



class MetricResult(BaseModel):
    metric_id: str
    principle: str
    priority: str
    status: str
    description: str
    evidence: Optional[str] = None
    recommendation: Optional[str] = None


class AssessmentReport(BaseModel):
    doi: str
    title: str = ""          # dataset title, empty when not available
    profile_name: str
    overall_score: float
    f_score: float
    a_score: float
    i_score: float
    r_score: float
    maturity_level: str = ""
    maturity_description: str = ""
    results: list[MetricResult]
