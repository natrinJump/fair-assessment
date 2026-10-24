from sqlmodel import SQLModel, create_engine, Session, Field
from typing import Optional

DATABASE_URL = "sqlite:///fair_assessment.db"
engine = create_engine(DATABASE_URL, echo=False)

class ProfileDB(SQLModel, table=True):
    __tablename__ = "profiledb"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    domain: str
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
    min_vocab_fairness_level: str = "none"
    # FAIR-Checker replication flags
    check_rdf_triples: bool = False
    min_url_authorities: int = 0
    require_dcat_properties: bool = False
    # F-UJI / I1 replication flag — where to detect file format
    #   "metadata"     : read from API response (default)
    #   "landing_page" : HTTP request to access URL (F-UJI style)
    #   "both"         : try metadata first, fall back to landing page
    i1_check_source: str = "metadata"
    # F-UJI / A1 replication flag — require explicit access level declaration
    check_access_level: bool = False
    # F-UJI / I2 replication flag — detect vocabs by namespace URI not keyword
    i2_namespace_check: bool = False
    # F-UJI / R1.1 replication flags
    r1_1_spdx_check: bool = False
    r1_1_require_license_uri: bool = False
    # F-UJI / R1.2 replication flag — require PROV-O or PAV ontology URI
    r1_2_require_prov_ontology: bool = False


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
    maturity_level: str = ""
    maturity_description: str = ""
    results_json: str
    profile_snapshot: str = "{}"
    created_at: str

def create_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
