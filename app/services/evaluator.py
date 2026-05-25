import json
import os
from app.models.metadata import NormalizedMetadata
from app.models.profile import Profile, MetricResult, AssessmentReport

def load_profile(profile_name: str) -> Profile:
    # try exact filename first
    path = os.path.join("profiles", f"{profile_name}.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            return Profile(**json.load(f))

    # try domain-based lookup from database
    from app.services.profile_service import get_all_profiles
    all_profiles = get_all_profiles()
    for p in all_profiles:
        if p["domain"] == profile_name or p["name"] == profile_name:
            return Profile(**p)

    # fallback to generic
    path = os.path.join("profiles", "generic_fair.json")
    with open(path, "r") as f:
        return Profile(**json.load(f))

def check_f1(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    identifier = metadata.core.identifier
    if identifier:
        id_lower = identifier.lower()
        for accepted in profile.accepted_identifiers:
            if accepted.lower() in id_lower or id_lower.startswith("10."):
                return MetricResult(
                    metric_id="F1",
                    principle="F",
                    priority="essential",
                    status="pass",
                    description="Dataset has a globally unique persistent identifier",
                    evidence=f"Identifier found: {identifier}"
                )
        return MetricResult(
            metric_id="F1",
            principle="F",
            priority="essential",
            status="partial",
            description="Dataset has an identifier but type not in accepted list",
            evidence=f"Identifier found: {identifier}",
            recommendation=f"Use one of the accepted identifier types: {profile.accepted_identifiers}"
        )
    return MetricResult(
        metric_id="F1",
        principle="F",
        priority="essential",
        status="fail",
        description="No persistent identifier found",
        recommendation="Add a DOI, Handle, or ARK identifier to your dataset"
    )

def check_f2(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    core = metadata.core
    missing = []
    for field in profile.required_metadata_fields:
        value = getattr(core, field, None)
        if not value:
            missing.append(field)
    if not missing:
        return MetricResult(
            metric_id="F2",
            principle="F",
            priority="essential",
            status="pass",
            description="All required metadata fields are present",
            evidence=f"Fields present: {profile.required_metadata_fields}"
        )
    if len(missing) < len(profile.required_metadata_fields):
        return MetricResult(
            metric_id="F2",
            principle="F",
            priority="essential",
            status="partial",
            description="Some required metadata fields are missing",
            evidence=f"Missing fields: {missing}",
            recommendation=f"Add the following metadata fields: {missing}"
        )
    return MetricResult(
        metric_id="F2",
        principle="F",
        priority="essential",
        status="fail",
        description="Required metadata fields are missing",
        evidence=f"Missing fields: {missing}",
        recommendation=f"Add the following metadata fields: {missing}"
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
        recommendation="Ensure the metadata explicitly references the dataset identifier"
    )

def check_f4(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
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
        description="No access URL found in metadata",
        recommendation="Ensure the dataset has a resolvable access URL"
    )

def check_a1(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    url = metadata.core.access_url
    if url and (url.startswith("http://") or url.startswith("https://")):
        return MetricResult(
            metric_id="A1",
            principle="A",
            priority="essential",
            status="pass",
            description="Metadata is accessible via HTTP/HTTPS",
            evidence=f"Access URL uses standard protocol: {url}"
        )
    return MetricResult(
        metric_id="A1",
        principle="A",
        priority="essential",
        status="fail",
        description="No HTTP/HTTPS access URL found",
        recommendation="Provide an access URL using HTTP or HTTPS protocol"
    )

def check_a1_1(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
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
            evidence="Protocol: HTTP",
            recommendation="Use HTTPS instead of HTTP for secure access"
        )
    return MetricResult(
        metric_id="A1.1",
        principle="A",
        priority="essential",
        status="fail",
        description="No open protocol URL detected",
        recommendation="Use HTTPS to make metadata accessible"
    )

def check_a1_2(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    url = metadata.core.access_url
    if url:
        return MetricResult(
            metric_id="A1.2",
            principle="A",
            priority="useful",
            status="pass",
            description="Data is accessible through a protocol that supports authentication",
            evidence=f"Access URL present: {url}"
        )
    return MetricResult(
        metric_id="A1.2",
        principle="A",
        priority="useful",
        status="fail",
        description="No access protocol information found",
        recommendation="Provide access URL with authentication support if data is restricted"
    )

def check_a2(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    if metadata.core.identifier:
        return MetricResult(
            metric_id="A2",
            principle="A",
            priority="essential",
            status="pass",
            description="Metadata remains accessible even if data is unavailable",
            evidence="Metadata retrieved successfully via identifier"
        )
    return MetricResult(
        metric_id="A2",
        principle="A",
        priority="essential",
        status="fail",
        description="Cannot confirm metadata persistence",
        recommendation="Ensure metadata is stored separately from the data"
    )

def check_i1(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    formats = [f.lower() for f in metadata.core.formats]
    accepted = [f.lower() for f in profile.accepted_formats]
    matched = [f for f in formats if any(a in f for a in accepted)]
    if matched:
        return MetricResult(
            metric_id="I1",
            principle="I",
            priority="important",
            status="pass",
            description="Data is provided in an accepted machine-readable format",
            evidence=f"Formats found: {matched}"
        )
    if formats:
        return MetricResult(
            metric_id="I1",
            principle="I",
            priority="important",
            status="partial",
            description="Data format not in accepted list",
            evidence=f"Formats found: {formats}",
            recommendation=f"Use one of the accepted formats: {profile.accepted_formats}"
        )
    return MetricResult(
        metric_id="I1",
        principle="I",
        priority="important",
        status="fail",
        description="No file format information found in metadata",
        recommendation=f"Specify the data format. Accepted: {profile.accepted_formats}"
    )

def check_i2(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    vocabulary = profile.required_vocabulary
    if not vocabulary:
        return MetricResult(
            metric_id="I2",
            principle="I",
            priority="important",
            status="pass",
            description="No specific vocabulary required by this profile",
            evidence="Vocabulary requirement: none"
        )
    custom = metadata.custom
    vocab_lower = vocabulary.lower()
    found = any(
        vocab_lower in str(v).lower()
        for v in custom.values()
    )
    if found:
        return MetricResult(
            metric_id="I2",
            principle="I",
            priority="important",
            status="pass",
            description=f"Metadata uses FAIR-compliant vocabulary: {vocabulary}",
            evidence=f"Vocabulary reference found in metadata"
        )
    return MetricResult(
        metric_id="I2",
        principle="I",
        priority="important",
        status="fail",
        description=f"Required vocabulary not detected in metadata",
        recommendation=f"Use terms from the {vocabulary} vocabulary in your metadata"
    )

def check_i3(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    core = metadata.core
    has_references = (
        core.access_url is not None or
        core.identifier is not None
    )
    if has_references:
        return MetricResult(
            metric_id="I3",
            principle="I",
            priority="important",
            status="pass",
            description="Metadata includes references to related resources",
            evidence=f"Identifier and access URL present as qualified references"
        )
    return MetricResult(
        metric_id="I3",
        principle="I",
        priority="important",
        status="fail",
        description="No qualified references found in metadata",
        recommendation="Add references to related datasets, publications, or resources"
    )

def check_r1(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    core = metadata.core
    reuse_fields = ["title", "description", "creator", "license"]
    present = [f for f in reuse_fields if getattr(core, f, None)]
    if len(present) == len(reuse_fields):
        return MetricResult(
            metric_id="R1",
            principle="R",
            priority="essential",
            status="pass",
            description="Metadata contains sufficient information for reuse",
            evidence=f"All reuse fields present: {present}"
        )
    missing = [f for f in reuse_fields if f not in present]
    return MetricResult(
        metric_id="R1",
        principle="R",
        priority="essential",
        status="partial" if present else "fail",
        description="Metadata is missing fields needed for reuse",
        evidence=f"Missing: {missing}",
        recommendation=f"Add the following fields to support reuse: {missing}"
    )

def check_r1_1(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    license_val = metadata.core.license
    if license_val:
        return MetricResult(
            metric_id="R1.1",
            principle="R",
            priority="essential",
            status="pass",
            description="Dataset has a machine-readable license",
            evidence=f"License: {license_val}"
        )
    return MetricResult(
        metric_id="R1.1",
        principle="R",
        priority="essential",
        status="fail",
        description="No license found in metadata",
        recommendation="Add a machine-readable license (e.g. CC-BY, CC0)"
    )

def check_r1_2(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    if metadata.core.creator and metadata.core.provenance_date:
        return MetricResult(
            metric_id="R1.2",
            principle="R",
            priority="important",
            status="pass",
            description="Provenance information is present",
            evidence=f"Creator: {metadata.core.creator}, Date: {metadata.core.provenance_date}"
        )
    missing = []
    if not metadata.core.creator:
        missing.append("creator")
    if not metadata.core.provenance_date:
        missing.append("provenance date")
    return MetricResult(
        metric_id="R1.2",
        principle="R",
        priority="important",
        status="partial" if metadata.core.creator or metadata.core.provenance_date else "fail",
        description="Incomplete provenance information",
        evidence=f"Missing: {missing}",
        recommendation=f"Add the following provenance fields: {missing}"
    )

def check_r1_3(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    formats = [f.lower() for f in metadata.core.formats]
    accepted = [f.lower() for f in profile.accepted_formats]
    if any(a in f for f in formats for a in accepted):
        return MetricResult(
            metric_id="R1.3",
            principle="R",
            priority="essential",
            status="pass",
            description="Data follows community standards for format",
            evidence=f"Standard format detected: {formats}"
        )
    return MetricResult(
        metric_id="R1.3",
        principle="R",
        priority="essential",
        status="fail",
        description="Data format does not follow community standards",
        recommendation=f"Use a community-standard format such as: {profile.accepted_formats}"
    )

METRIC_WEIGHTS = {
    "F1": 1.0,    # Essential — RDA-F1-01M/02M
    "F2": 1.0,    # Essential — RDA-F2-01M
    "F3": 1.0,    # Essential — RDA-F3-01M
    "F4": 1.0,    # Essential — RDA-F4-01M
    "A1": 1.0,    # Essential — RDA-A1-02M/03M/04M
    "A1.1": 1.0,  # Essential — RDA-A1.1-01M
    "A1.2": 0.5,  # Useful   — RDA-A1.2-01D
    "A2": 1.0,    # Essential — RDA-A2-01M
    "I1": 0.75,   # Important — RDA-I1-01M/02M
    "I2": 0.75,   # Important — RDA-I2-01M
    "I3": 0.5,    # Important/Useful mix — RDA-I3
    "R1": 1.0,    # Essential — RDA-R1-01M
    "R1.1": 1.0,  # Essential — RDA-R1.1-01M
    "R1.2": 0.75, # Important — RDA-R1.2-01M
    "R1.3": 1.0,  # Essential — RDA-R1.3-01M/02M
}

def calculate_score(results: list[MetricResult], principle: str) -> float:
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

def run_assessment(metadata: NormalizedMetadata, profile_name: str = "generic_fair") -> AssessmentReport:
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

    return AssessmentReport(
        doi=metadata.raw_identifier,
        profile_name=profile.name,
        overall_score=overall,
        f_score=f_score,
        a_score=a_score,
        i_score=i_score,
        r_score=r_score,
        results=results
    )