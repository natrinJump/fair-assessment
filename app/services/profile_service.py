import json
import os
from sqlmodel import Session, select
from app.db import ProfileDB, engine
from app.models.profile import Profile

def _db_to_dict(p: ProfileDB) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "domain": p.domain,
        "accepted_identifiers": json.loads(p.accepted_identifiers),
        "custom_identifiers": json.loads(p.custom_identifiers),
        "required_metadata_fields": json.loads(p.required_metadata_fields),
        "custom_metadata_fields": json.loads(p.custom_metadata_fields),
        "check_discoverability": p.check_discoverability,
        "accepted_formats": json.loads(p.accepted_formats),
        "required_vocabulary": p.required_vocabulary,
        "custom_vocabularies": json.loads(p.custom_vocabularies),
        "require_related_resources": p.require_related_resources,
        "accepted_licenses": json.loads(p.accepted_licenses),
        "required_license": p.required_license,
        "required_provenance_fields": json.loads(p.required_provenance_fields),
        "community_standard": p.community_standard,
        "min_vocab_fairness_level": p.min_vocab_fairness_level,
    }

def _dict_to_db(data: dict) -> ProfileDB:
    return ProfileDB(
        name=data["name"],
        domain=data["domain"],
        accepted_identifiers=json.dumps(data.get("accepted_identifiers", [])),
        custom_identifiers=json.dumps(data.get("custom_identifiers", [])),
        required_metadata_fields=json.dumps(
            data.get("required_metadata_fields", [])),
        custom_metadata_fields=json.dumps(
            data.get("custom_metadata_fields", [])),
        check_discoverability=data.get("check_discoverability", True),
        accepted_formats=json.dumps(data.get("accepted_formats", [])),
        required_vocabulary=data.get("required_vocabulary"),
        custom_vocabularies=json.dumps(data.get("custom_vocabularies", [])),
        require_related_resources=data.get("require_related_resources", False),
        accepted_licenses=json.dumps(data.get("accepted_licenses", [])),
        required_license=data.get("required_license"),
        required_provenance_fields=json.dumps(
            data.get("required_provenance_fields",
                     ["creator", "provenance_date"])),
        community_standard=data.get("community_standard"),
        min_vocab_fairness_level=data.get("min_vocab_fairness_level", "none"),
    )

def seed_profiles():
    with Session(engine) as session:
        existing = session.exec(select(ProfileDB)).all()
        if existing:
            return
        profiles_dir = "profiles"
        for filename in os.listdir(profiles_dir):
            if filename.endswith(".json"):
                with open(os.path.join(profiles_dir, filename), "r") as f:
                    data = json.load(f)
                session.add(_dict_to_db(data))
        session.commit()

def get_all_profiles():
    with Session(engine) as session:
        profiles = session.exec(select(ProfileDB)).all()
        return [_db_to_dict(p) for p in profiles]

def get_profile_by_name(name: str):
    with Session(engine) as session:
        results = session.exec(
            select(ProfileDB).where(ProfileDB.name == name)
        ).all()
        if not results:
            return None
        return _db_to_dict(results[0])

def get_profile_by_domain(domain: str):
    with Session(engine) as session:
        results = session.exec(
            select(ProfileDB).where(ProfileDB.domain == domain)
        ).all()
        if not results:
            return None
        return _db_to_dict(results[0])

def create_profile(data: dict) -> dict:
    with Session(engine) as session:
        profile = _dict_to_db(data)
        session.add(profile)
        session.commit()
        session.refresh(profile)
        return _db_to_dict(profile)

def update_profile(name: str, data: dict) -> dict:
    with Session(engine) as session:
        results = session.exec(
            select(ProfileDB).where(ProfileDB.name == name)
        ).all()
        if not results:
            return None
        p = results[0]
        for field in [
            "accepted_identifiers",
            "custom_identifiers",
            "required_metadata_fields",
            "custom_metadata_fields",
            "accepted_formats",
            "custom_vocabularies",
            "accepted_licenses",
            "required_provenance_fields",
        ]:
            if field in data:
                setattr(p, field, json.dumps(data[field]))
        for field in [
            "required_vocabulary",
            "required_license",
            "community_standard",
            "domain",
            "min_vocab_fairness_level",
        ]:
            if field in data:
                setattr(p, field, data[field])
        for field in ["check_discoverability", "require_related_resources"]:
            if field in data:
                setattr(p, field, data[field])
        session.add(p)
        session.commit()
        session.refresh(p)
        return _db_to_dict(p)

def delete_profile(name: str) -> bool:
    with Session(engine) as session:
        results = session.exec(
            select(ProfileDB).where(ProfileDB.name == name)
        ).all()
        if not results:
            return False
        session.delete(results[0])
        session.commit()
        return True