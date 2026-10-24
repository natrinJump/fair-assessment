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
        # FAIR-Checker replication flags
        "check_rdf_triples": p.check_rdf_triples,
        "min_url_authorities": p.min_url_authorities,
        "require_dcat_properties": p.require_dcat_properties,
        # Configurability flags
        "i1_check_source": p.i1_check_source,
        "check_access_level": p.check_access_level,
        "i2_namespace_check": p.i2_namespace_check,
        "r1_1_spdx_check": p.r1_1_spdx_check,
        "r1_1_require_license_uri": p.r1_1_require_license_uri,
        "r1_2_require_prov_ontology": p.r1_2_require_prov_ontology,
        "r1_check_measured_variables": p.r1_check_measured_variables,
        "required_community_standards": json.loads(p.required_community_standards),
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
        # FAIR-Checker replication flags
        check_rdf_triples=data.get("check_rdf_triples", False),
        min_url_authorities=data.get("min_url_authorities", 0),
        require_dcat_properties=data.get("require_dcat_properties", False),
        # F-UJI replication flags
        i1_check_source=data.get("i1_check_source", "metadata"),
        check_access_level=data.get("check_access_level", False),
        i2_namespace_check=data.get("i2_namespace_check", False),
        r1_1_spdx_check=data.get("r1_1_spdx_check", False),
        r1_1_require_license_uri=data.get("r1_1_require_license_uri", False),
        r1_2_require_prov_ontology=data.get("r1_2_require_prov_ontology", False),
        r1_check_measured_variables=data.get("r1_check_measured_variables", False),
        required_community_standards=json.dumps(
            data.get("required_community_standards", [])),
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
        # JSON-serialised list fields
        for field in [
            "accepted_identifiers",
            "custom_identifiers",
            "required_metadata_fields",
            "custom_metadata_fields",
            "accepted_formats",
            "custom_vocabularies",
            "accepted_licenses",
            "required_provenance_fields",
            "required_community_standards",
        ]:
            if field in data:
                setattr(p, field, json.dumps(data[field]))
        # Plain string fields
        for field in [
            "required_vocabulary",
            "required_license",
            "community_standard",
            "domain",
            "min_vocab_fairness_level",
            "i1_check_source",          # F-UJI: format detection source
        ]:
            if field in data:
                setattr(p, field, data[field])
        # Boolean fields
        for field in [
            "check_discoverability",
            "require_related_resources",
            # FAIR-Checker flags
            "check_rdf_triples",
            "require_dcat_properties",
            # F-UJI flags
            "check_access_level",
            "i2_namespace_check",
            "r1_1_spdx_check",
            "r1_1_require_license_uri",
            "r1_2_require_prov_ontology",
            "r1_check_measured_variables",
        ]:
            if field in data:
                setattr(p, field, data[field])
        # Integer fields
        if "min_url_authorities" in data:
            p.min_url_authorities = int(data["min_url_authorities"])
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
