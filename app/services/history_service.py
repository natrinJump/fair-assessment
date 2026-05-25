import json
from datetime import datetime
from sqlmodel import Session, select
from app.db import AssessmentHistoryDB, engine
from app.models.profile import AssessmentReport

def save_assessment(report: AssessmentReport):
    with Session(engine) as session:
        record = AssessmentHistoryDB(
            doi=report.doi,
            profile_name=report.profile_name,
            overall_score=report.overall_score,
            f_score=report.f_score,
            a_score=report.a_score,
            i_score=report.i_score,
            r_score=report.r_score,
            results_json=json.dumps([r.dict() for r in report.results]),
            created_at=datetime.now().isoformat(),
        )
        session.add(record)
        session.commit()

def get_history_by_doi(doi: str):
    with Session(engine) as session:
        records = session.exec(
            select(AssessmentHistoryDB)
            .where(AssessmentHistoryDB.doi == doi)
            .order_by(AssessmentHistoryDB.created_at)
        ).all()
        return [_to_dict(r) for r in records]

def get_assessment_by_id(id: int):
    with Session(engine) as session:
        record = session.get(AssessmentHistoryDB, id)
        if not record:
            return None
        return _to_dict(record)

def delete_assessment(id: int) -> bool:
    with Session(engine) as session:
        record = session.get(AssessmentHistoryDB, id)
        if not record:
            return False
        session.delete(record)
        session.commit()
        return True

def get_all_history():
    with Session(engine) as session:
        records = session.exec(
            select(AssessmentHistoryDB)
            .order_by(AssessmentHistoryDB.created_at.desc())
        ).all()
        return [_to_dict(r) for r in records]

def _to_dict(r: AssessmentHistoryDB):
    return {
        "id": r.id,
        "doi": r.doi,
        "profile_name": r.profile_name,
        "overall_score": r.overall_score,
        "f_score": r.f_score,
        "a_score": r.a_score,
        "i_score": r.i_score,
        "r_score": r.r_score,
        "created_at": r.created_at,
        "results": json.loads(r.results_json),
    }