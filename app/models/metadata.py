from pydantic import BaseModel
from typing import Optional

class CoreMetadata(BaseModel):
    identifier: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    creator: Optional[str] = None
    license: Optional[str] = None
    formats: list[str] = []
    access_url: Optional[str] = None
    provenance_date: Optional[str] = None

class NormalizedMetadata(BaseModel):
    source: str
    raw_identifier: str
    core: CoreMetadata
    custom: dict = {}