from fastapi import FastAPI, HTTPException
from app.services.retriever import fetch_by_doi
from app.services.normalizer import normalize_datacite, normalize_generic
from app.services.evaluator import run_assessment

app = FastAPI(title="FAIR Assessment API")

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
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get("/assess/{doi:path}")
async def assess(doi: str, profile: str = "generic_fair"):
    try:
        raw = await fetch_by_doi(doi)
        if raw["source"] == "datacite":
            normalized = normalize_datacite(raw, doi)
        else:
            normalized = normalize_generic(raw, doi)
        report = run_assessment(normalized, profile)
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")