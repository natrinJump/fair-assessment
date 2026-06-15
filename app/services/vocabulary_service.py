import httpx
from typing import Optional

# ── Known vocabulary FAIR scores ──────────────────────────────
# Pre-verified so we don't make slow HTTP calls for well-known vocabs
# Based on Cox et al. (2021) "Ten Simple Rules for Making a Vocabulary FAIR"
# Criteria: F1=resolvable URI, I1=machine-readable format,
#           R1.1=licence declared, A1=HTTPS accessible

KNOWN_VOCAB_FAIR = {
    "agrovoc": {
        "level": "full", "score": 90,
        "uri": "https://agrovoc.fao.org",
        "format": "SKOS/RDF",
        "license": "CC-BY IGO",
        "note": "FAO AGROVOC: HTTPS-resolvable, SKOS/RDF machine-readable, "
                "CC-BY IGO licence declared. Meets full FAIR vocabulary criteria."
    },
    "mesh": {
        "level": "full", "score": 85,
        "uri": "https://id.nlm.nih.gov/mesh/",
        "format": "RDF/N-Triples",
        "license": "Public Domain",
        "note": "MeSH: HTTPS-resolvable as Linked Data, RDF serialisation "
                "available, public domain. Meets full FAIR vocabulary criteria."
    },
    "envo": {
        "level": "full", "score": 90,
        "uri": "http://purl.obolibrary.org/obo/envo.owl",
        "format": "OWL/RDF",
        "license": "CC0",
        "note": "ENVO: Resolvable PURL, OWL/RDF machine-readable, CC0 licence. "
                "OBO Foundry member. Meets full FAIR vocabulary criteria."
    },
    "ddi": {
        "level": "standard", "score": 65,
        "uri": "https://ddialliance.org/",
        "format": "XML Schema",
        "license": "Open",
        "note": "DDI: HTTPS-resolvable, XML Schema available, open access. "
                "Explicit machine-readable RDF serialisation limited — "
                "meets standard but not full FAIR vocabulary criteria."
    },
    "schema.org": {
        "level": "full", "score": 95,
        "uri": "https://schema.org",
        "format": "JSON-LD/RDF/Turtle",
        "license": "CC-BY-SA",
        "note": "Schema.org: HTTPS-resolvable, multiple machine-readable "
                "serialisations (JSON-LD, RDF, Turtle), CC-BY-SA. "
                "Meets full FAIR vocabulary criteria."
    },
    "dublin core": {
        "level": "full", "score": 95,
        "uri": "http://purl.org/dc/terms/",
        "format": "RDF/OWL",
        "license": "Open",
        "note": "Dublin Core Terms: PURL-resolvable, RDF/OWL machine-readable, "
                "open. Foundational linked data vocabulary. "
                "Meets full FAIR vocabulary criteria."
    },
    "dcterms": {
        "level": "full", "score": 95,
        "uri": "http://purl.org/dc/terms/",
        "format": "RDF/OWL",
        "license": "Open",
        "note": "Dublin Core Terms: resolvable URI, RDF/OWL available, open. "
                "Meets full FAIR vocabulary criteria."
    },
    "skos": {
        "level": "full", "score": 90,
        "uri": "http://www.w3.org/2004/02/skos/core",
        "format": "RDF/OWL",
        "license": "Open (W3C)",
        "note": "SKOS: W3C standard, resolvable URI, RDF/OWL machine-readable, "
                "open W3C licence. Meets full FAIR vocabulary criteria."
    },
    "dcat": {
        "level": "full", "score": 90,
        "uri": "http://www.w3.org/ns/dcat#",
        "format": "RDF/OWL",
        "license": "Open (W3C)",
        "note": "DCAT: W3C standard, resolvable URI, RDF/OWL, open licence. "
                "Meets full FAIR vocabulary criteria."
    },
    "foaf": {
        "level": "full", "score": 85,
        "uri": "http://xmlns.com/foaf/0.1/",
        "format": "RDF/OWL",
        "license": "Open (CC-BY)",
        "note": "FOAF: Resolvable URI, RDF/OWL machine-readable, CC-BY. "
                "Meets full FAIR vocabulary criteria."
    },
}

LEVEL_ORDER = {"none": 0, "basic": 1, "standard": 2, "full": 3, "unknown": -1}
LEVEL_SCORE = {"none": 0, "basic": 40, "standard": 60, "full": 80}


def lookup_known_vocab(vocab_name: str) -> Optional[dict]:
    """Check if the vocabulary matches any known pre-verified entry."""
    name_lower = vocab_name.lower().strip()
    for key, data in KNOWN_VOCAB_FAIR.items():
        if key in name_lower or name_lower in key:
            return data
    return None


async def check_vocab_fairness_live(vocab: dict) -> dict:
    """
    Check the FAIRness of a custom vocabulary by testing its check_url.
    Returns a dict with level, score, and note.

    Criteria based on Cox et al. (2021) Ten Simple Rules for FAIR Vocabularies:
    - Basic (40%): Vocabulary URI resolves via HTTP
    - Standard (60%): Above + machine-readable format available
    - Full (80%): Above + licence information present
    """
    vocab_name = vocab.get("name", "unknown")
    check_url = vocab.get("check_url")

    if not check_url:
        return {
            "level": "unknown",
            "score": 0,
            "note": f"No check URL provided for vocabulary '{vocab_name}'. "
                    f"Add a check_url to enable FAIR vocabulary assessment."
        }

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                check_url,
                timeout=5.0,
                follow_redirects=True,
                headers={"Accept": "application/rdf+xml, text/turtle, "
                         "application/ld+json, application/json, text/html"}
            )

        if r.status_code != 200:
            return {
                "level": "fail",
                "score": 0,
                "uri": check_url,
                "note": f"Vocabulary URL returned HTTP {r.status_code}. "
                        f"URI is not resolvable — fails Basic FAIR criteria."
            }

        # Basic passed: URL resolves
        score = 40
        level = "basic"
        notes = [f"URI resolves (HTTP 200): {check_url}"]

        # Standard: machine-readable format check
        content_type = r.headers.get("content-type", "").lower()
        machine_readable = [
            "rdf", "turtle", "n-triples", "json-ld",
            "application/xml", "text/xml", "application/json",
            "application/ld+json", "text/turtle",
            "application/rdf+xml", "application/owl+xml"
        ]
        if any(t in content_type for t in machine_readable):
            score = 60
            level = "standard"
            notes.append(
                f"Machine-readable format detected "
                f"(Content-Type: {content_type.split(';')[0].strip()})"
            )

        # Full: licence information in response
        text = r.text[:5000].lower()
        licence_indicators = [
            "license", "licence", "creative commons", "cc-by", "cc0",
            "copyright", "rights", "dcterms:license", "schema:license",
            "dcterms:rights", "owl:versioninfo"
        ]
        if any(ind in text for ind in licence_indicators):
            score = 80
            level = "full"
            notes.append("Licence information detected in vocabulary response")

        return {
            "level": level,
            "score": score,
            "uri": check_url,
            "note": "; ".join(notes)
        }

    except httpx.TimeoutException:
        return {
            "level": "unknown",
            "score": 0,
            "uri": check_url,
            "note": f"Request to vocabulary URL timed out after 5s. "
                    f"Cannot assess FAIRness of '{vocab_name}'."
        }
    except Exception as e:
        return {
            "level": "unknown",
            "score": 0,
            "uri": check_url,
            "note": f"Could not reach vocabulary URL: {str(e)[:100]}"
        }


async def assess_vocab_fairness(profile) -> dict:
    """
    Run FAIR checks on all vocabularies declared in a profile.
    Returns a dict keyed by vocab name with the FAIR assessment result.
    Called from the assess endpoint before running the main evaluation.
    """
    results = {}

    # check required_vocabulary
    if profile.required_vocabulary:
        known = lookup_known_vocab(profile.required_vocabulary)
        if known:
            results[profile.required_vocabulary] = known
        else:
            # no known entry and no check_url — mark as unverified
            results[profile.required_vocabulary] = {
                "level": "unknown",
                "score": 0,
                "note": f"'{profile.required_vocabulary}' is not a pre-verified "
                        f"vocabulary. Add it as a custom vocabulary with a "
                        f"check_url to enable FAIRness assessment."
            }

    # check custom vocabularies
    for vocab in profile.custom_vocabularies:
        name = vocab.get("name", "")
        known = lookup_known_vocab(name)
        if known:
            results[name] = known
        else:
            results[name] = await check_vocab_fairness_live(vocab)

    return results


def meets_fairness_threshold(
    vocab_result: dict,
    min_level: str
) -> bool:
    """Check if a vocabulary result meets the minimum required level."""
    if min_level == "none":
        return True
    vocab_level = vocab_result.get("level", "unknown")
    return LEVEL_ORDER.get(vocab_level, -1) >= LEVEL_ORDER.get(min_level, 0)