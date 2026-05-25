import json
import os
from sqlmodel import Session, select
from app.db import ProfileDB, engine
from app.models.profile import Profile

def load_all_default_profiles():
    profiles_dir = "profiles"
    loaded = []
    for filename in os.listdir(profiles_dir):
        if filename.endswith(".json"):
            with open(os.path.join(profiles_dir, filename), "r") as f:
                data = json.load(f)
                loaded.append(data)
    return loaded

def seed_profiles():
    with Session(engine) as session:
        existing = session.exec(select(ProfileDB)).all()
        if existing:
            return
        for data in load_all_default_profiles():
            profile = ProfileDB(
                name=data["name"],
                domain=data["domain"],
                accepted_identifiers=json.dumps(data["accepted_identifiers"]),
                required_metadata_fields=json.dumps(data["required_metadata_fields"]),
                accepted_formats=json.dumps(data["accepted_formats"]),
                required_vocabulary=data.get("required_vocabulary"),
                required_license=data.get("required_license"),
            )
            session.add(profile)
        session.commit()

def get_all_profiles():
    with Session(engine) as session:
        profiles = session.exec(select(ProfileDB)).all()
        return [db_to_profile(p) for p in profiles]

def get_profile_by_name(name: str) -> Profile:
    with Session(engine) as session:
        results = session.exec(
            select(ProfileDB).where(ProfileDB.name == name)
        ).all()
        if not results:
            return None
        return db_to_profile(results[0])

def create_profile(data: dict) -> Profile:
    with Session(engine) as session:
        profile = ProfileDB(
            name=data["name"],
            domain=data["domain"],
            accepted_identifiers=json.dumps(data.get("accepted_identifiers", [])),
            required_metadata_fields=json.dumps(data.get("required_metadata_fields", [])),
            accepted_formats=json.dumps(data.get("accepted_formats", [])),
            required_vocabulary=data.get("required_vocabulary"),
            required_license=data.get("required_license"),
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)
        return db_to_profile(profile)

def update_profile(name: str, data: dict) -> Profile:
    with Session(engine) as session:
        results = session.exec(
            select(ProfileDB).where(ProfileDB.name == name)
        ).all()
        if not results:
            return None
        profile = results[0]
        if "accepted_identifiers" in data:
            profile.accepted_identifiers = json.dumps(data["accepted_identifiers"])
        if "required_metadata_fields" in data:
            profile.required_metadata_fields = json.dumps(data["required_metadata_fields"])
        if "accepted_formats" in data:
            profile.accepted_formats = json.dumps(data["accepted_formats"])
        if "required_vocabulary" in data:
            profile.required_vocabulary = data["required_vocabulary"]
        if "required_license" in data:
            profile.required_license = data["required_license"]
        session.add(profile)
        session.commit()
        session.refresh(profile)
        return db_to_profile(profile)

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

def db_to_profile(p: ProfileDB) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "domain": p.domain,
        "accepted_identifiers": json.loads(p.accepted_identifiers),
        "required_metadata_fields": json.loads(p.required_metadata_fields),
        "accepted_formats": json.loads(p.accepted_formats),
        "required_vocabulary": p.required_vocabulary,
        "required_license": p.required_license,
    }