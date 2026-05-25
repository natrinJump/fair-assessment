from sqlmodel import SQLModel, create_engine, Session, Field
from typing import Optional
import json

DATABASE_URL = "sqlite:///fair_assessment.db"
engine = create_engine(DATABASE_URL, echo=False)

class ProfileDB(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    domain: str
    accepted_identifiers: str  # stored as JSON string
    required_metadata_fields: str
    accepted_formats: str
    required_vocabulary: Optional[str] = None
    required_license: Optional[str] = None

class AssessmentHistoryDB(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    doi: str
    profile_name: str
    overall_score: float
    f_score: float
    a_score: float
    i_score: float
    r_score: float
    results_json: str  # full report stored as JSON string
    created_at: str

def create_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session