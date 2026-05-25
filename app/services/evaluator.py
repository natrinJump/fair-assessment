import json
import os
from app.models.metadata import NormalizedMetadata
from app.models.profile import Profile, MetricResult, AssessmentReport

def load_profile(profile_name: str) -> Profile:
    path = os.path.join("profiles", f"{profile_name}.json")
    if not os.path.exists(path):
        path = os.path.join("profiles", "generic_fair.json")
    with open(path, "r") as f:
        data = json.load(f)
    return Profile(**data)

def check_f1(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    identifier = metadata.core.identifier
    if identifier:
        id_lower = identifier.lower()
        for accepted in profile.accepted_identifiers:
            if accepted.lower() in id_lower or id_lower.startswith("10."):
                return MetricResult(
                    metric_id="F1",
                    principle="F",
                    status="pass",
                    description="Dataset has a globally unique persistent identifier",
                    evidence=f"Identifier found: {identifier}"
                )
        return MetricResult(
            metric_id="F1",
            principle="F",
            status="partial",
            description="Dataset has an identifier but type not in accepted list",
            evidence=f"Identifier found: {identifier}",
            recommendation=f"Use one of the accepted identifier types: {profile.accepted_identifiers}"
        )
    return MetricResult(
        metric_id="F1",
        principle="F",
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
            status="pass",
            description="All required metadata fields are present",
            evidence=f"Fields present: {profile.required_metadata_fields}"
        )
    if len(missing) < len(profile.required_metadata_fields):
        return MetricResult(
            metric_id="F2",
            principle="F",
            status="partial",
            description="Some required metadata fields are missing",
            evidence=f"Missing fields: {missing}",
            recommendation=f"Add the following metadata fields: {missing}"
        )
    return MetricResult(
        metric_id="F2",
        principle="F",
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
            status="pass",
            description="Metadata includes the identifier of the dataset",
            evidence=f"Identifier in metadata: {metadata.core.identifier}"
        )
    return MetricResult(
        metric_id="F3",
        principle="F",
        status="fail",
        description="Metadata does not include the dataset identifier",
        recommendation="Ensure the metadata explicitly references the dataset identifier"
    )

def check_f4(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    if metadata.core.access_url:
        return MetricResult(
            metric_id="F4",
            principle="F",
            status="pass",
            description="Metadata is retrievable via standard identifier",
            evidence=f"Access URL: {metadata.core.access_url}"
        )
    return MetricResult(
        metric_id="F4",
        principle="F",
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
            status="pass",
            description="Metadata is accessible via HTTP/HTTPS",
            evidence=f"Access URL uses standard protocol: {url}"
        )
    return MetricResult(
        metric_id="A1",
        principle="A",
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
            status="pass",
            description="Metadata uses open standard protocol (HTTPS)",
            evidence=f"Protocol: HTTPS"
        )
    if url and url.startswith("http://"):
        return MetricResult(
            metric_id="A1.1",
            principle="A",
            status="partial",
            description="Metadata uses HTTP instead of HTTPS",
            evidence=f"Protocol: HTTP",
            recommendation="Use HTTPS instead of HTTP for secure access"
        )
    return MetricResult(
        metric_id="A1.1",
        principle="A",
        status="fail",
        description="No open protocol URL detected",
        recommendation="Use HTTPS to make metadata accessible"
    )

def check_a2(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    if metadata.core.identifier:
        return MetricResult(
            metric_id="A2",
            principle="A",
            status="pass",
            description="Metadata remains accessible even if data is unavailable",
            evidence="Metadata retrieved successfully via identifier"
        )
    return MetricResult(
        metric_id="A2",
        principle="A",
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
            status="pass",
            description="Data is provided in an accepted machine-readable format",
            evidence=f"Formats found: {matched}"
        )
    if formats:
        return MetricResult(
            metric_id="I1",
            principle="I",
            status="partial",
            description="Data format not in accepted list",
            evidence=f"Formats found: {formats}",
            recommendation=f"Use one of the accepted formats: {profile.accepted_formats}"
        )
    return MetricResult(
        metric_id="I1",
        principle="I",
        status="fail",
        description="No file format information found in metadata",
        recommendation=f"Specify the data format. Accepted: {profile.accepted_formats}"
    )

def check_r1(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    core = metadata.core
    reuse_fields = ["title", "description", "creator", "license"]
    present = [f for f in reuse_fields if getattr(core, f, None)]
    if len(present) == len(reuse_fields):
        return MetricResult(
            metric_id="R1",
            principle="R",
            status="pass",
            description="Metadata contains sufficient information for reuse",
            evidence=f"All reuse fields present: {present}"
        )
    missing = [f for f in reuse_fields if f not in present]
    return MetricResult(
        metric_id="R1",
        principle="R",
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
            status="pass",
            description="Dataset has a machine-readable license",
            evidence=f"License: {license_val}"
        )
    return MetricResult(
        metric_id="R1.1",
        principle="R",
        status="fail",
        description="No license found in metadata",
        recommendation="Add a machine-readable license (e.g. CC-BY, CC0)"
    )

def check_r1_2(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
    if metadata.core.creator and metadata.core.provenance_date:
        return MetricResult(
            metric_id="R1.2",
            principle="R",
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
            status="pass",
            description="Data follows community standards for format",
            evidence=f"Standard format detected: {formats}"
        )
    return MetricResult(
        metric_id="R1.3",
        principle="R",
        status="fail",
        description="Data format does not follow community standards",
        recommendation=f"Use a community-standard format such as: {profile.accepted_formats}"
    )

def calculate_score(results: list[MetricResult], principle: str) -> float:
    principle_results = [r for r in results if r.principle == principle]
    if not principle_results:
        return 0.0
    score = 0.0
    for r in principle_results:
        if r.status == "pass":
            score += 1.0
        elif r.status == "partial":
            score += 0.5
    return round((score / len(principle_results)) * 100, 1)

def run_assessment(metadata: NormalizedMetadata, profile_name: str = "generic_fair") -> AssessmentReport:
    profile = load_profile(profile_name)

    results = [
        check_f1(metadata, profile),
        check_f2(metadata, profile),
        check_f3(metadata, profile),
        check_f4(metadata, profile),
        check_a1(metadata, profile),
        check_a1_1(metadata, profile),
        check_a2(metadata, profile),
        check_i1(metadata, profile),
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