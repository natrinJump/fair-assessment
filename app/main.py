from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.db import create_db
from app.services.retriever import fetch_by_doi
from app.services.normalizer import normalize_datacite, normalize_generic
from app.services.evaluator import run_assessment
from app.services.profile_service import (
    get_all_profiles, get_profile_by_name,
    create_profile, update_profile,
    delete_profile, seed_profiles
)
from app.services.history_service import (
    save_assessment, get_history_by_doi, get_all_history,
    get_assessment_by_id, delete_assessment
)


def normalize_by_source(raw: dict, doi: str):
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
async def assess(doi: str, profile: str = "generic_fair"):
    try:
        raw = await fetch_by_doi(doi)
        normalized = normalize_by_source(raw, doi)
        report = run_assessment(normalized, profile)
        save_assessment(report)
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
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