import httpx

DATACITE_API = "https://api.datacite.org/dois/{doi}"

async def fetch_by_doi(doi: str) -> dict:
    clean = doi.replace("https://doi.org/", "").strip()

    async with httpx.AsyncClient() as client:
        r = await client.get(
            DATACITE_API.format(doi=clean),
            headers={"Accept": "application/json"},
            timeout=10.0
        )
        if r.status_code == 200:
            return {"source": "datacite", "data": r.json()}

        r2 = await client.get(
            f"https://doi.org/{clean}",
            headers={"Accept": "application/json"},
            follow_redirects=True,
            timeout=10.0
        )
        if r2.status_code == 200:
            return {"source": "generic", "data": r2.json()}

    raise ValueError(f"Could not retrieve metadata for DOI: {doi}")