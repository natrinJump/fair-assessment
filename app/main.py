from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.db import create_db
from app.services.retriever import fetch_by_doi
from app.services.normalizer import normalize_datacite, normalize_generic
from app.services.evaluator import run_assessment
from app.services.profile_service import (
    get_all_profiles, get_profile_by_name,
    create_profile, update_profile,
    delete_profile, seed_profiles,
    get_profile_by_domain
)
from app.services.history_service import (
    save_assessment, get_history_by_doi, get_all_history,
    get_assessment_by_id, delete_assessment
)

def get_custom_fields_for_profile(profile_name: str) -> list:
    profile_data = get_profile_by_domain(profile_name)
    if not profile_data:
        profile_data = get_profile_by_name(profile_name)
    if profile_data:
        return (
            profile_data.get("custom_metadata_fields", []) +
            profile_data.get("required_metadata_fields", [])
        )
    return []

def generate_turtle(profile: dict) -> str:
    name = profile["name"]
    domain = profile["domain"]
    base_uri = f"https://w3id.org/fair/fip/example/{domain}"
    profile_uri = f"{base_uri}/profile"

    lines = []

    # prefixes
    lines.append("@prefix fip: <https://w3id.org/fair/fip/terms/> .")
    lines.append("@prefix dcterms: <http://purl.org/dc/terms/> .")
    lines.append("@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .")
    lines.append("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .")
    lines.append("@prefix fair: <https://w3id.org/fair/principles/terms/> .")
    lines.append("")

    # profile declaration
    lines.append(f"<{profile_uri}>")
    lines.append(f"    a fip:FAIR-Enabling-Resource ;")
    lines.append(f"    dcterms:title \"{name}\" ;")
    lines.append(f"    dcterms:description \"FAIR Implementation Profile "
                 f"for {domain} domain\" ;")
    lines.append(f"    dcterms:subject \"{domain}\" ;")

    # add declarations
    declarations = []

    # F1 — identifiers
    for pid in profile.get("accepted_identifiers", []):
        declarations.append(f"{base_uri}#f1-{pid}")
    for c in profile.get("custom_identifiers", []):
        declarations.append(f"{base_uri}#f1-custom-{c.get('name','').replace(' ','-')}")

    # F2 — metadata fields
    for field in profile.get("required_metadata_fields", []):
        declarations.append(f"{base_uri}#f2-{field}")
    for field in profile.get("custom_metadata_fields", []):
        declarations.append(f"{base_uri}#f2-custom-{field}")

    # I1 — formats
    for fmt in profile.get("accepted_formats", []):
        declarations.append(f"{base_uri}#i1-{fmt.replace('-','_')}")

    # I2 — vocabularies
    if profile.get("required_vocabulary"):
        declarations.append(f"{base_uri}#i2-vocab")
    for v in profile.get("custom_vocabularies", []):
        declarations.append(
            f"{base_uri}#i2-custom-{v.get('name','').replace(' ','-')}")

    # R1.1 — licenses
    for lic in profile.get("accepted_licenses", []):
        declarations.append(f"{base_uri}#r1-license-{lic.replace('-','_')}")

    for d in declarations:
        lines.append(f"    fip:declares-current-use-of <{d}> ;")

    lines[-1] = lines[-1].rstrip(" ;") + " ."
    lines.append("")

    # F1 identifier declarations
    lines.append(f"# F1 — Identifier")
    for pid in profile.get("accepted_identifiers", []):
        uri = f"{base_uri}#f1-{pid}"
        lines.append(f"<{uri}>")
        lines.append(f"    a fip:FIP-Declaration ;")
        lines.append(f"    fip:principle-tag \"F1\" ;")
        lines.append(f"    dcterms:description "
                     f"\"Accepted persistent identifier: {pid}\" ;")
        lines.append(f"    rdfs:label \"{pid.upper()} identifier\" .")
        lines.append("")

    for c in profile.get("custom_identifiers", []):
        cname = c.get("name", "")
        cval = c.get("value", "")
        ctype = c.get("match_type", "contains")
        uri = f"{base_uri}#f1-custom-{cname.replace(' ','-')}"
        lines.append(f"<{uri}>")
        lines.append(f"    a fip:FIP-Declaration ;")
        lines.append(f"    fip:principle-tag \"F1\" ;")
        lines.append(f"    dcterms:description "
                     f"\"Custom identifier: {cname} "
                     f"({ctype}: {cval})\" ;")
        lines.append(f"    rdfs:label \"{cname} (custom)\" .")
        lines.append("")

    # F2 metadata fields
    lines.append(f"# F2 — Metadata Fields")
    for field in (profile.get("required_metadata_fields", []) +
                  profile.get("custom_metadata_fields", [])):
        is_custom = field in profile.get("custom_metadata_fields", [])
        uri = f"{base_uri}#f2-{'custom-' if is_custom else ''}{field}"
        lines.append(f"<{uri}>")
        lines.append(f"    a fip:FIP-Declaration ;")
        lines.append(f"    fip:principle-tag \"F2\" ;")
        lines.append(f"    dcterms:description "
                     f"\"Required metadata field: {field}"
                     f"{'(domain-specific)' if is_custom else ''}\" ;")
        lines.append(f"    rdfs:label \"{field}\" .")
        lines.append("")

    # I1 formats
    lines.append(f"# I1 — Formats")
    for fmt in profile.get("accepted_formats", []):
        uri = f"{base_uri}#i1-{fmt.replace('-','_')}"
        lines.append(f"<{uri}>")
        lines.append(f"    a fip:FIP-Declaration ;")
        lines.append(f"    fip:principle-tag \"I1\" ;")
        lines.append(f"    dcterms:description "
                     f"\"Accepted file format: {fmt}\" ;")
        lines.append(f"    rdfs:label \"{fmt}\" .")
        lines.append("")

    # I2 vocabularies
    lines.append(f"# I2 — Vocabularies")
    if profile.get("required_vocabulary"):
        vocab = profile["required_vocabulary"]
        uri = f"{base_uri}#i2-vocab"
        lines.append(f"<{uri}>")
        lines.append(f"    a fip:FIP-Declaration ;")
        lines.append(f"    fip:principle-tag \"I2\" ;")
        lines.append(f"    dcterms:description "
                     f"\"Required vocabulary: {vocab}\" ;")
        lines.append(f"    rdfs:label \"{vocab}\" .")
        lines.append("")

    for v in profile.get("custom_vocabularies", []):
        vname = v.get("name", "")
        vkws = ", ".join(v.get("keywords", []))
        uri = f"{base_uri}#i2-custom-{vname.replace(' ','-')}"
        lines.append(f"<{uri}>")
        lines.append(f"    a fip:FIP-Declaration ;")
        lines.append(f"    fip:principle-tag \"I2\" ;")
        lines.append(f"    dcterms:description "
                     f"\"Custom vocabulary: {vname}. "
                     f"Keywords: {vkws}\" ;")
        lines.append(f"    rdfs:label \"{vname} (custom)\" .")
        lines.append("")

    # R1.1 licenses
    lines.append(f"# R1.1 — Licenses")
    for lic in profile.get("accepted_licenses", []):
        uri = f"{base_uri}#r1-license-{lic.replace('-','_')}"
        lines.append(f"<{uri}>")
        lines.append(f"    a fip:FIP-Declaration ;")
        lines.append(f"    fip:principle-tag \"R1.1\" ;")
        lines.append(f"    dcterms:description "
                     f"\"Accepted license: {lic}\" ;")
        lines.append(f"    rdfs:label \"{lic}\" .")
        lines.append("")

    # R1.2 provenance
    lines.append(f"# R1.2 — Provenance")
    for field in profile.get("required_provenance_fields", []):
        uri = f"{base_uri}#r1-2-{field}"
        lines.append(f"<{uri}>")
        lines.append(f"    a fip:FIP-Declaration ;")
        lines.append(f"    fip:principle-tag \"R1.2\" ;")
        lines.append(f"    dcterms:description "
                     f"\"Required provenance field: {field}\" ;")
        lines.append(f"    rdfs:label \"{field}\" .")
        lines.append("")

    # R1.3 community standard
    if profile.get("community_standard"):
        std = profile["community_standard"]
        uri = f"{base_uri}#r1-3-standard"
        lines.append(f"# R1.3 — Community Standard")
        lines.append(f"<{uri}>")
        lines.append(f"    a fip:FIP-Declaration ;")
        lines.append(f"    fip:principle-tag \"R1.3\" ;")
        lines.append(f"    dcterms:description "
                     f"\"Community standard: {std}\" ;")
        lines.append(f"    rdfs:label \"{std}\" .")
        lines.append("")

    return "\n".join(lines)

def normalize_by_source(raw: dict, doi: str, custom_fields: list = None):
    from app.services.normalizer import (
        normalize_datacite, normalize_generic, normalize_ark, normalize_url
    )
    source = raw.get("source", "generic")
    if source == "datacite":
        return normalize_datacite(raw, doi)
    elif source == "ark":
        return normalize_ark(raw, doi)
    elif source == "url":
        return normalize_url(raw, doi)
    else:
        return normalize_generic(raw, doi)
    
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db()
    seed_profiles()
    yield

app = FastAPI(title="FAIR Assessment API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "FAIR Assessment API is running"}

@app.get("/metadata/{doi:path}")
async def get_metadata(doi: str):
    try:
        raw = await fetch_by_doi(doi)
        normalized = normalize_by_source(raw, doi)
        return normalized
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/assess/{doi:path}")
async def assess(doi: str, profile: str = "generic"):
    try:
        raw = await fetch_by_doi(doi)
        custom_fields = get_custom_fields_for_profile(profile)
        normalized = normalize_by_source(raw, doi, custom_fields)
        report = run_assessment(normalized, profile)
        # removed save_assessment — history saved locally in browser
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/assess/upload")
async def assess_upload(
    file: UploadFile = File(...),
    profile: str = "generic"
):
    try:
        content = await file.read()
        filename = file.filename.lower()
        from app.services.normalizer import normalize_from_upload
        normalized = normalize_from_upload(content, filename, profile)
        report = run_assessment(normalized, profile)

        profile_data = get_profile_by_domain(profile)
        if not profile_data:
            profile_data = get_profile_by_name(profile)

        save_assessment(report, profile_snapshot=profile_data)
        return report
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/profiles")
def list_profiles():
    return get_all_profiles()

@app.get("/profiles/{name}")
def get_profile(name: str):
    profile = get_profile_by_name(name)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile

@app.post("/profiles")
def add_profile(data: dict):
    try:
        return create_profile(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/profiles/{name}")
def edit_profile(name: str, data: dict):
    updated = update_profile(name, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Profile not found")
    return updated

@app.post("/profiles/{name}/restore")
def restore_profile(name: str):
    import json, os
    profile = get_profile_by_name(name)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # try domain name first, then common variations
    domain = profile["domain"]
    candidates = [
        f"{domain}.json",
        f"{domain}_fair.json",
        "generic_fair.json" if domain == "generic" else None,
        f"{name.lower().replace(' ', '_')}.json",
    ]
    
    path = None
    for candidate in candidates:
        if candidate:
            p = os.path.join("profiles", candidate)
            if os.path.exists(p):
                path = p
                break
    
    if not path:
        raise HTTPException(status_code=404,
            detail=f"No original file found for domain: {domain}")
    
    with open(path, "r") as f:
        original = json.load(f)
    
    updated = update_profile(name, {
        "accepted_identifiers": original["accepted_identifiers"],
        "required_metadata_fields": original["required_metadata_fields"],
        "accepted_formats": original["accepted_formats"],
        "required_vocabulary": original.get("required_vocabulary"),
        "required_license": original.get("required_license"),
    })
    return updated

@app.get("/profiles/{name}/export/turtle")
def export_profile_turtle(name: str):
    from fastapi.responses import Response
    profile = get_profile_by_name(name)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    turtle = generate_turtle(profile)
    return Response(
        content=turtle,
        media_type="text/turtle",
        headers={
            "Content-Disposition": 
                f'attachment; filename="{name.replace(" ", "_")}_FIP.ttl"'
        }
    )

@app.delete("/profiles/{name}")
def remove_profile(name: str):
    success = delete_profile(name)
    if not success:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"message": f"Profile '{name}' deleted"}

@app.get("/history")
def list_history():
    return get_all_history()

@app.get("/history/run/{id}")
def get_run(id: int):
    run = get_assessment_by_id(id)
    if not run:
        raise HTTPException(status_code=404, detail="Assessment run not found")
    return run

@app.delete("/history/run/{id}")
def delete_run(id: int):
    success = delete_assessment(id)
    if not success:
        raise HTTPException(status_code=404, detail="Assessment run not found")
    return {"message": "Assessment deleted"}

@app.get("/history/{doi:path}")
def get_doi_history(doi: str):
    history = get_history_by_doi(doi)
    if not history:
        raise HTTPException(status_code=404, detail="No history found for this DOI")
    return history