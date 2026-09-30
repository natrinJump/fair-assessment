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

    # F2 — FAIR-Checker style: require DCAT/Dublin Core RDF properties
    require_dcat_properties: bool = False

    # F4 — discoverability
    check_discoverability: bool = True

    # I1 — formats
    accepted_formats: list[str] = []

    # I1 — FAIR-Checker style: pass if RDF/JSON-LD detected on landing page
    check_rdf_triples: bool = False

    # I2 — vocabularies
    required_vocabulary: Optional[str] = None
    custom_vocabularies: list[dict] = []
    min_vocab_fairness_level: str = "none"

    # I3 — qualified references
    require_related_resources: bool = False

    # I3 — FAIR-Checker style: fail if fewer than N distinct URL domains
    min_url_authorities: int = 0

    # R1.1 — licenses
    accepted_licenses: list[str] = []
    required_license: Optional[str] = None

    # R1.2 — provenance fields
    required_provenance_fields: list[str] = ["creator", "provenance_date"]

    # R1.3 — community standards
    community_standard: Optional[str] = None


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
    profile_name: str
    overall_score: float
    f_score: float
    a_score: float
    i_score: float
    r_score: float
    maturity_level: str = ""
    maturity_description: str = ""
    results: list[MetricResult]
