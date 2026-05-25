from fastapi import FastAPI, HTTPException
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
    save_assessment, get_history_by_doi, get_all_history
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db()
    seed_profiles()
    yield

app = FastAPI(title="FAIR Assessment API", lifespan=lifespan)

@app.get("/")
def root():
    return {"message": "FAIR Assessment API is running"}

@app.get("/metadata/{doi:path}")
async def get_metadata(doi: str):
    try:
        raw = await fetch_by_doi(doi)
        if raw["source"] == "datacite":
            normalized = normalize_datacite(raw, doi)
        else:
            normalized = normalize_generic(raw, doi)
        return normalized
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/assess/{doi:path}")
async def assess(doi: str, profile: str = "generic_fair"):
    try:
        raw = await fetch_by_doi(doi)
        if raw["source"] == "datacite":
            normalized = normalize_datacite(raw, doi)
        else:
            normalized = normalize_generic(raw, doi)
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

@app.delete("/profiles/{name}")
def remove_profile(name: str):
    success = delete_profile(name)
    if not success:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"message": f"Profile '{name}' deleted"}

@app.get("/history")
def list_history():
    return get_all_history()

@app.get("/history/{doi:path}")
def get_doi_history(doi: str):
    history = get_history_by_doi(doi)
    if not history:
        raise HTTPException(status_code=404, detail="No history found for this DOI")
    return history