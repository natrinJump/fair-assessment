"""
Unit tests for app/services/evaluator.py

Tests each metric check function with known metadata inputs
and asserts expected outputs. No database or external API calls.

Run with:
    pytest tests/test_evaluator.py -v

Install pytest first if needed:
    pip install pytest --break-system-packages
"""

import pytest
from app.models.profile import Profile, MetricResult
from app.models.metadata import NormalizedMetadata, CoreMetadata
from app.services.evaluator import (
    check_f1, check_f2, check_f3, check_f4,
    check_a1, check_a1_1, check_a1_2, check_a2,
    check_i1, check_i2, check_i3,
    check_r1, check_r1_1, check_r1_2, check_r1_3,
    calculate_score, get_maturity,
)


# ── Helpers ────────────────────────────────────────────────────

def make_metadata(
    identifier="10.5281/zenodo.123456",
    title="Test Dataset",
    description="A test dataset for unit testing",
    creator="Test Author",
    license="https://creativecommons.org/licenses/by/4.0/",
    formats=None,
    access_url="https://doi.org/10.5281/zenodo.123456",
    provenance_date="2024-01-01",
    custom=None,
    source="test",
) -> NormalizedMetadata:
    return NormalizedMetadata(
        source=source,
        raw_identifier=identifier or "",
        core=CoreMetadata(
            identifier=identifier,
            title=title,
            description=description,
            creator=creator,
            license=license,
            formats=formats if formats is not None else [],
            access_url=access_url,
            provenance_date=provenance_date,
        ),
        custom=custom if custom is not None else {},
    )


def make_profile(
    name="Test Profile",
    domain="test",
    accepted_identifiers=None,
    custom_identifiers=None,
    required_metadata_fields=None,
    custom_metadata_fields=None,
    check_discoverability=True,
    accepted_formats=None,
    required_vocabulary=None,
    custom_vocabularies=None,
    min_vocab_fairness_level="none",
    require_related_resources=False,
    accepted_licenses=None,
    required_license=None,
    required_provenance_fields=None,
    community_standard=None,
) -> Profile:
    return Profile(
        name=name,
        domain=domain,
        accepted_identifiers=accepted_identifiers if accepted_identifiers is not None else ["doi", "url"],
        custom_identifiers=custom_identifiers if custom_identifiers is not None else [],
        required_metadata_fields=required_metadata_fields if required_metadata_fields is not None else ["title", "description", "creator", "license"],
        custom_metadata_fields=custom_metadata_fields if custom_metadata_fields is not None else [],
        check_discoverability=check_discoverability,
        accepted_formats=accepted_formats if accepted_formats is not None else ["csv", "json", "xml", "json-ld"],
        required_vocabulary=required_vocabulary,
        custom_vocabularies=custom_vocabularies if custom_vocabularies is not None else [],
        min_vocab_fairness_level=min_vocab_fairness_level,
        require_related_resources=require_related_resources,
        accepted_licenses=accepted_licenses if accepted_licenses is not None else ["cc-by", "cc0", "mit"],
        required_license=required_license,
        required_provenance_fields=required_provenance_fields if required_provenance_fields is not None else ["creator", "provenance_date"],
        community_standard=community_standard,
    )


# ── F1 Tests ───────────────────────────────────────────────────

class TestF1:

    def test_pass_doi_identifier(self):
        meta = make_metadata(identifier="10.5281/zenodo.123456")
        profile = make_profile(accepted_identifiers=["doi"])
        result = check_f1(meta, profile)
        assert result.status == "pass"
        assert result.metric_id == "F1"
        assert "doi" in result.evidence.lower()

    def test_pass_ark_identifier(self):
        meta = make_metadata(identifier="ark:/12345/fk4abc123")
        profile = make_profile(accepted_identifiers=["ark"])
        result = check_f1(meta, profile)
        assert result.status == "pass"
        assert "ark" in result.evidence.lower()

    def test_pass_handle_identifier(self):
        meta = make_metadata(identifier="hdl:20.500.12345/abc")
        profile = make_profile(accepted_identifiers=["handle"])
        result = check_f1(meta, profile)
        assert result.status == "pass"

    def test_pass_w3id_identifier(self):
        meta = make_metadata(
            identifier="https://w3id.org/FAIR-course-UT/dataset1"
        )
        profile = make_profile(accepted_identifiers=["w3id", "url"])
        result = check_f1(meta, profile)
        assert result.status == "pass"

    def test_pass_url_identifier(self):
        meta = make_metadata(identifier="https://example.org/dataset/1")
        profile = make_profile(accepted_identifiers=["url"])
        result = check_f1(meta, profile)
        assert result.status == "pass"

    def test_fail_no_identifier(self):
        meta = make_metadata(identifier="")
        profile = make_profile(accepted_identifiers=["doi"])
        result = check_f1(meta, profile)
        assert result.status == "fail"
        assert result.recommendation is not None

    def test_fail_wrong_identifier_type(self):
        meta = make_metadata(identifier="ark:/12345/fk4abc123")
        profile = make_profile(accepted_identifiers=["doi"])
        result = check_f1(meta, profile)
        assert result.status == "fail"
        assert "ark" in result.evidence.lower()

    def test_pass_custom_identifier_starts_with(self):
        meta = make_metadata(identifier="my-repo:dataset-001")
        profile = make_profile(
            accepted_identifiers=[],
            custom_identifiers=[{
                "name": "myrepo",
                "match_type": "starts_with",
                "value": "my-repo:"
            }]
        )
        result = check_f1(meta, profile)
        assert result.status == "pass"

    def test_pass_custom_identifier_regex(self):
        meta = make_metadata(identifier="DS-2024-001")
        profile = make_profile(
            accepted_identifiers=[],
            custom_identifiers=[{
                "name": "ds-id",
                "match_type": "regex",
                "value": r"^ds-\d{4}-\d{3}$"
            }]
        )
        result = check_f1(meta, profile)
        assert result.status == "pass"

    def test_pass_biosample_identifier(self):
        meta = make_metadata(identifier="SAMN12345678")
        profile = make_profile(accepted_identifiers=["biosample"])
        result = check_f1(meta, profile)
        assert result.status == "pass"


# ── F2 Tests ───────────────────────────────────────────────────

class TestF2:

    def test_pass_all_fields_present(self):
        meta = make_metadata(
            title="Test", description="Desc",
            creator="Author", license="cc-by"
        )
        profile = make_profile(
            required_metadata_fields=["title", "description",
                                      "creator", "license"]
        )
        result = check_f2(meta, profile)
        assert result.status == "pass"

    def test_partial_some_fields_missing(self):
        meta = make_metadata(title="Test", description="Desc",
                             creator="", license="")
        profile = make_profile(
            required_metadata_fields=["title", "description",
                                      "creator", "license"]
        )
        result = check_f2(meta, profile)
        assert result.status == "partial"
        assert "creator" in result.evidence
        assert "license" in result.evidence

    def test_fail_no_fields_present(self):
        meta = make_metadata(title="", description="",
                             creator="", license="")
        profile = make_profile(
            required_metadata_fields=["title", "description",
                                      "creator", "license"]
        )
        result = check_f2(meta, profile)
        assert result.status == "fail"

    def test_pass_no_required_fields_configured(self):
        meta = make_metadata()
        profile = make_profile(
            required_metadata_fields=[],
            custom_metadata_fields=[]
        )
        result = check_f2(meta, profile)
        assert result.status == "pass"

    def test_partial_custom_domain_field_missing(self):
        meta = make_metadata()
        profile = make_profile(
            required_metadata_fields=["title", "description",
                                      "creator", "license"],
            custom_metadata_fields=["crop_type"]
        )
        result = check_f2(meta, profile)
        assert result.status == "partial"
        assert "crop_type" in result.evidence

    def test_deduplication_no_duplicate_fields(self):
        meta = make_metadata()
        profile = make_profile(
            required_metadata_fields=["title", "creator"],
            custom_metadata_fields=["title"]
        )
        result = check_f2(meta, profile)
        assert result.evidence.count("title") == 1


# ── F3 Tests ───────────────────────────────────────────────────

class TestF3:

    def test_pass_identifier_and_url_present(self):
        meta = make_metadata(
            identifier="10.5281/zenodo.123",
            access_url="https://doi.org/10.5281/zenodo.123"
        )
        result = check_f3(meta, make_profile())
        assert result.status == "pass"
        assert "10.5281/zenodo.123" in result.evidence

    def test_fail_no_identifier(self):
        meta = make_metadata(identifier="", access_url="")
        result = check_f3(meta, make_profile())
        assert result.status == "fail"

    def test_fail_no_access_url(self):
        meta = make_metadata(
            identifier="10.5281/zenodo.123",
            access_url=""
        )
        result = check_f3(meta, make_profile())
        assert result.status == "fail"


# ── F4 Tests ───────────────────────────────────────────────────

class TestF4:

    def test_pass_access_url_present(self):
        meta = make_metadata(
            access_url="https://doi.org/10.5281/zenodo.123"
        )
        result = check_f4(meta, make_profile(check_discoverability=True))
        assert result.status == "pass"

    def test_fail_no_access_url(self):
        meta = make_metadata(access_url="")
        result = check_f4(meta, make_profile(check_discoverability=True))
        assert result.status == "fail"

    def test_pass_discoverability_disabled(self):
        meta = make_metadata(access_url="")
        result = check_f4(meta, make_profile(check_discoverability=False))
        assert result.status == "pass"
        assert "disabled" in result.description.lower()


# ── A1 Tests ───────────────────────────────────────────────────

class TestA1:

    def test_pass_https_url(self):
        meta = make_metadata(access_url="https://example.org/dataset")
        assert check_a1(meta, make_profile()).status == "pass"

    def test_pass_http_url(self):
        meta = make_metadata(access_url="http://example.org/dataset")
        assert check_a1(meta, make_profile()).status == "pass"

    def test_fail_no_url(self):
        meta = make_metadata(access_url="")
        assert check_a1(meta, make_profile()).status == "fail"


# ── A1.1 Tests ─────────────────────────────────────────────────

class TestA1_1:

    def test_pass_https(self):
        meta = make_metadata(access_url="https://example.org/dataset")
        result = check_a1_1(meta, make_profile())
        assert result.status == "pass"
        assert "HTTPS" in result.evidence

    def test_partial_http(self):
        meta = make_metadata(access_url="http://example.org/dataset")
        result = check_a1_1(meta, make_profile())
        assert result.status == "partial"
        assert "HTTP" in result.evidence

    def test_fail_no_url(self):
        meta = make_metadata(access_url="")
        assert check_a1_1(meta, make_profile()).status == "fail"


# ── A1.2 Tests ─────────────────────────────────────────────────

class TestA1_2:

    def test_pass_cc_by_license(self):
        meta = make_metadata(
            license="https://creativecommons.org/licenses/by/4.0/"
        )
        assert check_a1_2(meta, make_profile()).status == "pass"

    def test_pass_cc0_license(self):
        meta = make_metadata(
            license="https://creativecommons.org/publicdomain/zero/1.0/"
        )
        assert check_a1_2(meta, make_profile()).status == "pass"

    def test_partial_url_but_no_open_license(self):
        meta = make_metadata(
            license="custom proprietary license",
            access_url="https://example.org/dataset"
        )
        assert check_a1_2(meta, make_profile()).status == "partial"

    def test_fail_no_license_no_url(self):
        meta = make_metadata(license="", access_url="")
        assert check_a1_2(meta, make_profile()).status == "fail"


# ── A2 Tests ───────────────────────────────────────────────────

class TestA2:

    def test_pass_identifier_url_and_title(self):
        meta = make_metadata(
            identifier="10.5281/zenodo.123",
            access_url="https://doi.org/10.5281/zenodo.123",
            title="My Dataset"
        )
        result = check_a2(meta, make_profile())
        assert result.status == "pass"
        assert "My Dataset" in result.evidence

    def test_partial_no_title(self):
        meta = make_metadata(
            identifier="10.5281/zenodo.123",
            access_url="https://doi.org/10.5281/zenodo.123",
            title=""
        )
        assert check_a2(meta, make_profile()).status == "partial"

    def test_fail_no_identifier(self):
        meta = make_metadata(identifier="", access_url="")
        assert check_a2(meta, make_profile()).status == "fail"


# ── I1 Tests ───────────────────────────────────────────────────

class TestI1:

    def test_pass_csv_format_accepted(self):
        meta = make_metadata(formats=["text/csv"])
        profile = make_profile(accepted_formats=["csv", "json"])
        result = check_i1(meta, profile)
        assert result.status == "pass"
        assert "csv" in result.evidence.lower()

    def test_pass_json_ld_format_accepted(self):
        # Use "json-ld" string which matches the accepted format directly
        meta = make_metadata(formats=["json-ld"])
        profile = make_profile(accepted_formats=["json-ld", "rdf"])
        result = check_i1(meta, profile)
        assert result.status == "pass"

    def test_partial_format_present_but_not_accepted(self):
        meta = make_metadata(formats=["application/zip"])
        profile = make_profile(accepted_formats=["csv", "json-ld"])
        result = check_i1(meta, profile)
        assert result.status == "partial"
        assert "zip" in result.evidence.lower()

    def test_fail_no_format_declared(self):
        meta = make_metadata(formats=[])
        profile = make_profile(accepted_formats=["csv", "json"])
        result = check_i1(meta, profile)
        assert result.status == "fail"
        assert result.recommendation is not None


# ── I2 Tests ───────────────────────────────────────────────────

class TestI2:

    def test_pass_no_vocab_required_schema_org_detected(self):
        meta = make_metadata(
            description="Dataset using schema.org vocabulary"
        )
        result = check_i2(meta, make_profile(required_vocabulary=None))
        assert result.status == "pass"
        assert "schema.org" in result.evidence.lower()

    def test_partial_no_vocab_required_none_detected(self):
        meta = make_metadata(
            description="A dataset with no vocabulary references"
        )
        result = check_i2(meta, make_profile(required_vocabulary=None))
        assert result.status == "partial"

    def test_pass_required_vocab_detected(self):
        meta = make_metadata(
            description="Agricultural dataset annotated with agrovoc "
                        "controlled vocabulary from FAO"
        )
        result = check_i2(meta, make_profile(required_vocabulary="AGROVOC"))
        assert result.status == "pass"

    def test_fail_required_vocab_not_detected(self):
        meta = make_metadata(
            description="A crop yield dataset with no vocabulary reference"
        )
        result = check_i2(meta, make_profile(required_vocabulary="AGROVOC"))
        assert result.status == "fail"
        assert "AGROVOC" in result.evidence

    def test_partial_some_vocabs_detected_some_not(self):
        meta = make_metadata(
            description="Biodiversity dataset using darwin core schema"
        )
        profile = make_profile(
            required_vocabulary="Gene Ontology",
            custom_vocabularies=[{
                "name": "Darwin Core",
                "keywords": ["darwin core", "dwc:"],
                "check_url": None
            }]
        )
        result = check_i2(meta, profile)
        assert result.status == "partial"

    def test_pass_vocab_detected_and_fairness_level_met(self):
        meta = make_metadata(
            description="Agricultural dataset annotated with agrovoc vocabulary"
        )
        profile = make_profile(
            required_vocabulary="AGROVOC",
            min_vocab_fairness_level="standard"
        )
        vocab_fairness = {
            "AGROVOC": {"level": "full", "score": 90, "note": "Pre-verified"}
        }
        result = check_i2(meta, profile, vocab_fairness=vocab_fairness)
        assert result.status == "pass"
        assert "full" in result.evidence.lower()

    def test_partial_vocab_detected_but_fairness_level_not_met(self):
        meta = make_metadata(
            description="Survey dataset using ddialliance.org standard"
        )
        profile = make_profile(
            required_vocabulary="DDI",
            min_vocab_fairness_level="full"
        )
        vocab_fairness = {
            "DDI": {"level": "standard", "score": 65,
                    "note": "DDI is at standard level"}
        }
        result = check_i2(meta, profile, vocab_fairness=vocab_fairness)
        assert result.status == "partial"
        assert "standard" in result.evidence.lower()
        assert "full" in result.evidence.lower()

    def test_no_double_counting_required_vocab_in_custom(self):
        meta = make_metadata(
            description="Dataset using agrovoc controlled vocabulary"
        )
        profile = make_profile(
            required_vocabulary="AGROVOC",
            custom_vocabularies=[{
                "name": "AGROVOC",
                "keywords": ["agrovoc"],
                "check_url": None
            }]
        )
        result = check_i2(meta, profile)
        assert result.evidence.count("AGROVOC") <= 1


# ── I3 Tests ───────────────────────────────────────────────────

class TestI3:

    def test_pass_related_identifier_in_custom(self):
        meta = make_metadata(
            custom={"relatedIdentifier": "10.5281/zenodo.111"}
        )
        result = check_i3(meta, make_profile(require_related_resources=False))
        assert result.status == "pass"

    def test_partial_no_references_not_required(self):
        meta = make_metadata(custom={})
        result = check_i3(meta, make_profile(require_related_resources=False))
        assert result.status == "partial"

    def test_fail_no_references_required(self):
        meta = make_metadata(custom={})
        result = check_i3(meta, make_profile(require_related_resources=True))
        assert result.status == "fail"


# ── R1 Tests ───────────────────────────────────────────────────

class TestR1:

    def test_pass_all_fields_present(self):
        meta = make_metadata(
            title="Test", description="Desc",
            creator="Author", license="cc-by"
        )
        profile = make_profile(
            required_metadata_fields=["title", "description",
                                      "creator", "license"],
            custom_metadata_fields=[]
        )
        assert check_r1(meta, profile).status == "pass"

    def test_partial_some_missing(self):
        meta = make_metadata(title="Test", creator="", license="")
        profile = make_profile(
            required_metadata_fields=["title", "creator", "license"]
        )
        assert check_r1(meta, profile).status == "partial"

    def test_fail_all_missing(self):
        meta = make_metadata(title="", creator="",
                             description="", license="")
        profile = make_profile(
            required_metadata_fields=["title", "creator",
                                      "description", "license"]
        )
        assert check_r1(meta, profile).status == "fail"

    def test_uses_default_fields_when_none_configured(self):
        meta = make_metadata(title="Test", description="Desc",
                             creator="Author", license="cc-by")
        profile = make_profile(
            required_metadata_fields=[],
            custom_metadata_fields=[]
        )
        assert check_r1(meta, profile).status == "pass"


# ── R1.1 Tests ─────────────────────────────────────────────────

class TestR1_1:

    def test_pass_cc_by_in_accepted_list(self):
        meta = make_metadata(
            license="https://creativecommons.org/licenses/by/4.0/"
        )
        profile = make_profile(accepted_licenses=["cc-by", "cc0"])
        assert check_r1_1(meta, profile).status == "pass"

    def test_pass_cc0_in_accepted_list(self):
        meta = make_metadata(
            license="https://creativecommons.org/publicdomain/zero/1.0/"
        )
        profile = make_profile(accepted_licenses=["cc-by", "cc0"])
        assert check_r1_1(meta, profile).status == "pass"

    def test_fail_no_license(self):
        meta = make_metadata(license="")
        profile = make_profile(accepted_licenses=["cc-by"])
        assert check_r1_1(meta, profile).status == "fail"

    def test_partial_license_not_in_accepted_list(self):
        meta = make_metadata(
            license="https://opendatacommons.org/licenses/by/1.0/"
        )
        profile = make_profile(accepted_licenses=["cc-by", "cc0"])
        result = check_r1_1(meta, profile)
        assert result.status == "partial"
        assert "not in accepted list" in result.description.lower()

    def test_partial_required_license_not_matched(self):
        # Profile requires CC-BY specifically but dataset has CC0
        meta = make_metadata(
            license="https://creativecommons.org/publicdomain/zero/1.0/"
        )
        profile = make_profile(
            accepted_licenses=["cc-by", "cc0"],
            required_license="cc-by"
        )
        result = check_r1_1(meta, profile)
        assert result.status == "partial"
        assert "requires" in result.recommendation.lower()

    def test_pass_no_accepted_list_any_license(self):
        # Empty accepted list — any license should pass
        meta = make_metadata(license="some custom open license")
        profile = make_profile(accepted_licenses=[])
        assert check_r1_1(meta, profile).status == "pass"


# ── R1.2 Tests ─────────────────────────────────────────────────

class TestR1_2:

    def test_pass_all_provenance_fields_present(self):
        meta = make_metadata(creator="Author", provenance_date="2024-01-01")
        profile = make_profile(
            required_provenance_fields=["creator", "provenance_date"]
        )
        assert check_r1_2(meta, profile).status == "pass"

    def test_partial_some_provenance_missing(self):
        meta = make_metadata(creator="Author", provenance_date="")
        profile = make_profile(
            required_provenance_fields=["creator", "provenance_date"]
        )
        result = check_r1_2(meta, profile)
        assert result.status == "partial"
        assert "provenance_date" in result.evidence

    def test_fail_no_provenance(self):
        meta = make_metadata(creator="", provenance_date="")
        profile = make_profile(
            required_provenance_fields=["creator", "provenance_date"]
        )
        assert check_r1_2(meta, profile).status == "fail"


# ── R1.3 Tests ─────────────────────────────────────────────────

class TestR1_3:

    def test_pass_format_matches_community_standard(self):
        meta = make_metadata(formats=["text/csv"])
        profile = make_profile(
            accepted_formats=["csv"],
            community_standard="CF Conventions"
        )
        result = check_r1_3(meta, profile)
        assert result.status == "pass"
        assert "CF Conventions" in result.description

    def test_fail_format_not_in_accepted_list(self):
        meta = make_metadata(formats=["application/zip"])
        profile = make_profile(accepted_formats=["csv", "netcdf"])
        result = check_r1_3(meta, profile)
        assert result.status == "fail"
        assert "zip" in result.evidence.lower()

    def test_fail_no_format_declared(self):
        meta = make_metadata(formats=[])
        profile = make_profile(accepted_formats=["csv"])
        assert check_r1_3(meta, profile).status == "fail"


# ── Scoring Tests ──────────────────────────────────────────────

class TestScoring:

    def test_calculate_score_all_pass(self):
        results = [
            MetricResult(metric_id="F1", principle="F",
                         priority="essential", status="pass", description=""),
            MetricResult(metric_id="F2", principle="F",
                         priority="essential", status="pass", description=""),
        ]
        assert calculate_score(results, "F") == 100.0

    def test_calculate_score_all_fail(self):
        results = [
            MetricResult(metric_id="F1", principle="F",
                         priority="essential", status="fail", description=""),
            MetricResult(metric_id="F2", principle="F",
                         priority="essential", status="fail", description=""),
        ]
        assert calculate_score(results, "F") == 0.0

    def test_calculate_score_partial_earns_half(self):
        results = [
            MetricResult(metric_id="F1", principle="F",
                         priority="essential", status="partial",
                         description=""),
        ]
        assert calculate_score(results, "F") == 50.0

    def test_calculate_score_empty_principle(self):
        assert calculate_score([], "F") == 0.0

    def test_get_maturity_advanced(self):
        level, _ = get_maturity(85.0)
        assert level == "Advanced"

    def test_get_maturity_intermediate(self):
        level, _ = get_maturity(70.0)
        assert level == "Intermediate"

    def test_get_maturity_initial(self):
        level, _ = get_maturity(45.0)
        assert level == "Initial"

    def test_get_maturity_incomplete(self):
        level, _ = get_maturity(20.0)
        assert level == "Incomplete"

    def test_get_maturity_boundary_80(self):
        level, _ = get_maturity(80.0)
        assert level == "Advanced"

    def test_get_maturity_boundary_60(self):
        level, _ = get_maturity(60.0)
        assert level == "Intermediate"

    def test_get_maturity_boundary_40(self):
        level, _ = get_maturity(40.0)
        assert level == "Initial"


# ── Domain Profile Integration Tests ──────────────────────────

class TestDomainProfileIntegration:

    def test_agriculture_profile_missing_domain_fields(self):
        meta = make_metadata(
            title="Crop Yield Dataset",
            description="Agricultural measurements",
            creator="Author",
            license="https://creativecommons.org/licenses/by/4.0/"
        )
        profile = make_profile(
            required_metadata_fields=["title", "description",
                                      "creator", "license"],
            custom_metadata_fields=["crop_type", "soil_type",
                                    "spatial_coverage"]
        )
        result = check_f2(meta, profile)
        assert result.status == "partial"
        assert "crop_type" in result.evidence
        assert "soil_type" in result.evidence

    def test_agriculture_profile_agrovoc_not_detected(self):
        meta = make_metadata(
            description="A dataset about crop yield measurements"
        )
        result = check_i2(meta, make_profile(required_vocabulary="AGROVOC"))
        assert result.status == "fail"
        assert "AGROVOC" in result.evidence

    def test_agriculture_profile_cc_by_required_cc0_fails(self):
        meta = make_metadata(
            license="https://creativecommons.org/publicdomain/zero/1.0/"
        )
        profile = make_profile(
            accepted_licenses=["cc-by", "cc0"],
            required_license="cc-by"
        )
        assert check_r1_1(meta, profile).status == "partial"

    def test_social_sciences_ddi_detected_passes_i2(self):
        meta = make_metadata(
            description="Survey dataset structured according to "
                        "ddialliance.org metadata standard"
        )
        result = check_i2(meta, make_profile(required_vocabulary="DDI"))
        assert result.status == "pass"

    def test_odc_by_not_accepted_social_sciences(self):
        meta = make_metadata(
            license="https://opendatacommons.org/licenses/by/1.0/"
        )
        profile = make_profile(accepted_licenses=["cc-by", "cc0"])
        assert check_r1_1(meta, profile).status == "partial"

    def test_pangaea_zip_format_partial_environmental(self):
        meta = make_metadata(formats=["application/zip"])
        profile = make_profile(accepted_formats=["netcdf", "csv", "json-ld"])
        result = check_i1(meta, profile)
        assert result.status == "partial"
        assert "zip" in result.evidence.lower()

    def test_generic_profile_passes_where_domain_fails(self):
        meta = make_metadata(
            title="Test", description="Desc",
            creator="Author", license="cc-by"
        )
        generic_profile = make_profile(
            required_metadata_fields=["title", "description",
                                      "creator", "license"],
            custom_metadata_fields=[]
        )
        agriculture_profile = make_profile(
            required_metadata_fields=["title", "description",
                                      "creator", "license"],
            custom_metadata_fields=["crop_type", "soil_type"]
        )
        assert check_f2(meta, generic_profile).status == "pass"
        assert check_f2(meta, agriculture_profile).status == "partial"
