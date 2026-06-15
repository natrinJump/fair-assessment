import json
import os
import re
from app.models.metadata import NormalizedMetadata
from app.models.profile import Profile, MetricResult, AssessmentReport


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

    if not all_required:
        return MetricResult(
            metric_id="F2",
            principle="F",
            priority="essential",
            status="pass",
            description="No specific metadata fields required by this profile",
            evidence="No required fields configured"
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
            evidence=f"Present: {', '.join(present)}"
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
                f"Missing: {', '.join(missing)}",
            recommendation=f"Add missing fields: {', '.join(missing)}." + note
        )
    return MetricResult(
        metric_id="F2",
        principle="F",
        priority="essential",
        status="fail",
        description="All required metadata fields are missing",
        evidence=f"Missing: {', '.join(missing)}",
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
    url = metadata.core.access_url
    if url and (url.startswith("http://") or url.startswith("https://")):
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
    formats = [f.lower() for f in metadata.core.formats]
    accepted = [f.lower() for f in profile.accepted_formats]
    matched = [f for f in formats if any(a in f or f in a for a in accepted)]
    if matched:
        return MetricResult(
            metric_id="I1",
            principle="I",
            priority="important",
            status="pass",
            description="Data is in an accepted machine-readable format",
            evidence=f"Format detected: {', '.join(matched)}"
        )
    if formats:
        return MetricResult(
            metric_id="I1",
            principle="I",
            priority="important",
            status="partial",
            description="Format present but not in accepted list",
            evidence=f"Current format: {', '.join(formats)}",
            recommendation=f"Format '{', '.join(formats)}' not accepted. "
                f"This profile requires one of: "
                f"{', '.join(profile.accepted_formats)}"
        )
    return MetricResult(
        metric_id="I1",
        principle="I",
        priority="important",
        status="fail",
        description="No file format information found in metadata",
        recommendation=f"Specify the data format. "
            f"This profile accepts: {', '.join(profile.accepted_formats)}"
    )


def check_i2(metadata: NormalizedMetadata, profile: Profile) -> MetricResult:
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
        search_text = (str(metadata.core.dict()).lower() +
                       str(metadata.custom).lower())
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

    if not missing:
        return MetricResult(
            metric_id="R1",
            principle="R",
            priority="essential",
            status="pass",
            description="Metadata contains sufficient information for reuse",
            evidence=f"All reuse fields present: {', '.join(present)}"
        )
    if present:
        return MetricResult(
            metric_id="R1",
            principle="R",
            priority="essential",
            status="partial",
            description="Metadata missing some fields needed for reuse",
            evidence=f"Present: {', '.join(present)} | "
                f"Missing: {', '.join(missing)}",
            recommendation=f"Add missing fields: {', '.join(missing)}"
        )
    return MetricResult(
        metric_id="R1",
        principle="R",
        priority="essential",
        status="fail",
        description="Metadata missing fields needed for reuse",
        evidence=f"Missing: {', '.join(missing)}",
        recommendation=f"Add required fields: {', '.join(all_fields)}"
    )


def check_r1_1(metadata: NormalizedMetadata,
               profile: Profile) -> MetricResult:
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
    core = metadata.core
    required_fields = profile.required_provenance_fields
    field_map = {
        "creator": core.creator,
        "provenance_date": core.provenance_date,
        "description": core.description,
        "title": core.title,
    }

    present = []
    missing = []
    for field in required_fields:
        val = field_map.get(field) or metadata.custom.get(field)
        if val:
            present.append(field)
        else:
            missing.append(field)

    if not missing:
        return MetricResult(
            metric_id="R1.2",
            principle="R",
            priority="important",
            status="pass",
            description="All required provenance information is present",
            evidence=f"Provenance fields: {', '.join(present)}"
        )
    if present:
        return MetricResult(
            metric_id="R1.2",
            principle="R",
            priority="important",
            status="partial",
            description="Incomplete provenance information",
            evidence=f"Present: {', '.join(present)} | "
                f"Missing: {', '.join(missing)}",
            recommendation=f"Add missing provenance: {', '.join(missing)}"
        )
    return MetricResult(
        metric_id="R1.2",
        principle="R",
        priority="important",
        status="fail",
        description="No provenance information found",
        evidence=f"Missing: {', '.join(missing)}",
        recommendation=f"Add provenance fields: "
            f"{', '.join(required_fields)}"
    )


def check_r1_3(metadata: NormalizedMetadata,
               profile: Profile) -> MetricResult:
    formats = [f.lower() for f in metadata.core.formats]
    accepted = [f.lower() for f in profile.accepted_formats]
    standard = profile.community_standard
    matched = [f for f in formats if any(a in f or f in a for a in accepted)]

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
    if formats:
        return MetricResult(
            metric_id="R1.3",
            principle="R",
            priority="essential",
            status="fail",
            description="Data format does not match community standards",
            evidence=f"Current format: {', '.join(formats)}",
            recommendation=f"Format '{', '.join(formats)}' not accepted. "
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
                   profile_name: str = "generic") -> AssessmentReport:
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
