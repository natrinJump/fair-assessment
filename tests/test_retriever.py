import pytest
import httpx
from app.services.retriever import fetch_by_doi
from app.services.normalizer import normalize_datacite

@pytest.mark.asyncio
async def test_fetch_real_doi():
    result = await fetch_by_doi("10.5281/zenodo.3490058")
    assert result is not None
    assert "source" in result
    assert "data" in result

@pytest.mark.asyncio
async def test_normalize_datacite():
    result = await fetch_by_doi("10.5281/zenodo.3490058")
    if result["source"] == "datacite":
        normalized = normalize_datacite(result, "10.5281/zenodo.3490058")
        assert normalized.core.identifier is not None
        assert normalized.source == "datacite"

@pytest.mark.asyncio
async def test_invalid_doi():
    with pytest.raises(ValueError):
        await fetch_by_doi("this-is-not-a-doi")