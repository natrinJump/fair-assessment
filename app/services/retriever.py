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


async def fetch_jsonld(doi_url: str) -> dict:
    """
    Fetch JSON-LD from the dataset landing page via content negotiation.
    This replicates what FAIR-Checker does to detect schema.org vocabulary
    references and encoding formats not exposed by the DataCite API.
    Returns empty dict on any failure — always safe to call.
    """
    try:
        headers = {'Accept': 'application/ld+json'}
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                doi_url, headers=headers,
                follow_redirects=True, timeout=10
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {}


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
                # Also fetch JSON-LD from landing page
                doi_url = f"https://doi.org/{clean}"
                jsonld = await fetch_jsonld(doi_url)
                return {
                    "source": "datacite",
                    "data": r.json(),
                    "jsonld": jsonld
                }

            # fallback: resolve via doi.org
            r2 = await client.get(
                f"https://doi.org/{clean}",
                headers={"Accept": "application/vnd.datacite.datacite+json"},
                follow_redirects=True,
                timeout=10.0
            )
            if r2.status_code == 200:
                try:
                    doi_url = f"https://doi.org/{clean}"
                    jsonld = await fetch_jsonld(doi_url)
                    return {
                        "source": "datacite",
                        "data": {"data": {"attributes": r2.json()}},
                        "jsonld": jsonld
                    }
                except Exception:
                    pass

        # ARK identifier
        if "ark:" in clean.lower() or "n2t.net" in clean.lower():
            ark_url = doi if doi.startswith("http") else f"https://n2t.net/{clean}"
            r = await client.get(
                ark_url,
                headers={"Accept": "application/json, text/html"},
                follow_redirects=True,
                timeout=10.0
            )
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
                },
                "jsonld": {}
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
                    return {
                        "source": "generic",
                        "data": r.json(),
                        "jsonld": {}
                    }
                except Exception:
                    pass

        # Direct URL fallback
        if doi.startswith("http"):
            r = await client.get(
                doi,
                headers={"Accept": "application/json"},
                follow_redirects=True,
                timeout=10.0
            )
            if r.status_code == 200:
                try:
                    return {
                        "source": "generic",
                        "data": r.json(),
                        "jsonld": {}
                    }
                except Exception:
                    pass
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
                },
                "jsonld": {}
            }

    raise ValueError(
        f"Could not retrieve metadata for: {doi}. "
        f"Supported: DOI (10.xxxx/xxx), ARK (ark:/), Handle (hdl:), or URL"
    )
