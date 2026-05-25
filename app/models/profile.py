from pydantic import BaseModel
from typing import Optional

class MetricRule(BaseModel):
    id: str
    principle: str
    field: str
    condition: str
    accepted_values: list[str] = []
    weight: float = 1.0
    description: str

class Profile(BaseModel):
    name: str
    domain: str
    accepted_identifiers: list[str] = []
    required_metadata_fields: list[str] = []
    accepted_formats: list[str] = []
    required_vocabulary: Optional[str] = None
    required_license: Optional[str] = None

class MetricResult(BaseModel):
    metric_id: str
    principle: str
    status: str
    description: str
    evidence: Optional[str] = None
    recommendation: Optional[str] = None

class AssessmentReport(BaseModel):
    doi: str
    profile_name: str
    overall_score: float
    f_score: float
    a_score: float
    i_score: float
    r_score: float
    results: list[MetricResult]