import httpx
import re

DATACITE_API = "https://api.datacite.org/dois/{doi}"

def clean_identifier(identifier: str) -> str:
    identifier = identifier.strip()
    for prefix in ["https://doi.org/", "http://doi.org/",
                   "https://hdl.handle.net/", "http://hdl.handle.net/"]:
        if identifier.startswith(prefix):
            identifier = identifier[len(prefix):]
    return identifier

async def fetch_by_doi(doi: str) -> dict:
    clean = clean_identifier(doi)

    async with httpx.AsyncClient() as client:

        # DOI — try DataCite API first
        if clean.startswith("10.") or "doi" in clean.lower():
            r = await client.get(
                DATACITE_API.format(doi=clean),
                headers={"Accept": "application/json"},
                timeout=10.0
            )
            if r.status_code == 200:
                return {"source": "datacite", "data": r.json()}

            # fallback: resolve via doi.org
            r2 = await client.get(
                f"https://doi.org/{clean}",
                headers={"Accept": "application/vnd.datacite.datacite+json"},
                follow_redirects=True,
                timeout=10.0
            )
            if r2.status_code == 200:
                try:
                    return {"source": "datacite",
                            "data": {"data": {"attributes": r2.json()}}}
                except Exception:
                    pass

        # ARK identifier — resolve via n2t.net and extract what we can
        if "ark:" in clean.lower() or "n2t.net" in clean.lower():
            ark_url = doi if doi.startswith("http") else f"https://n2t.net/{clean}"
            r = await client.get(
                ark_url,
                headers={"Accept": "application/json, text/html"},
                follow_redirects=True,
                timeout=10.0
            )
            # build minimal metadata from what we resolved
            final_url = str(r.url)
            return {
                "source": "ark",
                "data": {
                    "identifier": clean,
                    "access_url": final_url,
                    "title": None,
                    "description": None,
                    "creator": None,
                    "license": None,
                    "formats": [],
                    "provenance_date": None
                }
            }

        # Handle identifier
        if clean.startswith("hdl:") or "handle" in clean.lower():
            handle = clean.replace("hdl:", "")
            r = await client.get(
                f"https://hdl.handle.net/{handle}",
                headers={"Accept": "application/json"},
                follow_redirects=True,
                timeout=10.0
            )
            if r.status_code == 200:
                try:
                    return {"source": "generic", "data": r.json()}
                except Exception:
                    pass

        # direct URL fallback
        if doi.startswith("http"):
            r = await client.get(
                doi,
                headers={"Accept": "application/json"},
                follow_redirects=True,
                timeout=10.0
            )
            if r.status_code == 200:
                try:
                    return {"source": "generic", "data": r.json()}
                except Exception:
                    pass
            # even if no JSON, return minimal metadata from resolved URL
            return {
                "source": "url",
                "data": {
                    "identifier": doi,
                    "access_url": str(r.url),
                    "title": None,
                    "description": None,
                    "creator": None,
                    "license": None,
                    "formats": [],
                    "provenance_date": None
                }
            }

    raise ValueError(
        f"Could not retrieve metadata for: {doi}. "
        f"Supported: DOI (10.xxxx/xxx), ARK (ark:/), Handle (hdl:), or URL"
    )