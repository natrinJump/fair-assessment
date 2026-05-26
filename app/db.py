from sqlmodel import SQLModel, create_engine, Session, Field
from typing import Optional

DATABASE_URL = "sqlite:///fair_assessment.db"
engine = create_engine(DATABASE_URL, echo=False)

class ProfileDB(SQLModel, table=True):
    __tablename__ = "profiledb"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    domain: str
    # stored as JSON strings
    accepted_identifiers: str = "[]"
    custom_identifiers: str = "[]"
    required_metadata_fields: str = "[]"
    custom_metadata_fields: str = "[]"
    check_discoverability: bool = True
    accepted_formats: str = "[]"
    required_vocabulary: Optional[str] = None
    custom_vocabularies: str = "[]"
    require_related_resources: bool = False
    accepted_licenses: str = "[]"
    required_license: Optional[str] = None
    required_provenance_fields: str = '["creator", "provenance_date"]'
    community_standard: Optional[str] = None

class AssessmentHistoryDB(SQLModel, table=True):
    __tablename__ = "assessmenthistorydb"
    id: Optional[int] = Field(default=None, primary_key=True)
    doi: str
    profile_name: str
    overall_score: float
    f_score: float
    a_score: float
    i_score: float
    r_score: float
    results_json: str
    created_at: str

def create_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session