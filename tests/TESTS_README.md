# ProFAIR Unit Tests

## Overview

The unit test suite verifies the correctness of ProFAIR's evaluation engine.
It covers all 15 FAIR metric check functions with known inputs and expected
outputs. Tests run directly against the metric functions without any database
or external API calls, making them fast and fully reproducible.

**52 tests total — all should pass.**

---

## What is tested

| Metric group | Scenarios | Tests |
|---|---|---|
| F1 | DOI, ARK, Handle, W3ID, URL, BioSample; missing identifier; wrong type; custom prefix and regex rules | 10 |
| F2 | All fields present; partial; all missing; no fields configured; custom domain fields; deduplication | 6 |
| F3, F4 | Identifier and URL present; missing; discoverability disabled | 6 |
| A1, A1.1, A1.2, A2 | HTTPS, HTTP, no URL; open and proprietary licences; title presence | 12 |
| I1 | Accepted format; not accepted; no format declared | 4 |
| I2 | No vocabulary required; detected; not detected; partial detection; vocabulary FAIR level met and not met; deduplication | 8 |
| I3 | Related identifier present; not present; required | 3 |
| R1, R1.1, R1.2, R1.3 | Full and partial presence; licence matching; required licence; provenance; format standards | 13 |
| Scoring | All pass, all fail, partial scoring; maturity level boundaries (40, 60, 80) | 11 |

The final class (`TestDomainProfileIntegration`) contains integration tests
that replicate real-world assessment scenarios: the same dataset returns
different results under Generic vs domain-specific profiles, confirming that
profile configuration correctly controls metric outcomes.

---

## Requirements

Install dependencies from the project root:

```bash
pip install -r requirements.txt
pip install pytest
```

Or if you are using a virtual environment:

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install pytest
```

---

## How to run

From the project root directory (`fair-assessment/`):

```bash
# Run all 52 tests
pytest tests/test_evaluator.py -v

# Run a specific metric class only
pytest tests/test_evaluator.py::TestF1 -v
pytest tests/test_evaluator.py::TestI2 -v

# Run with short output (no verbose)
pytest tests/test_evaluator.py

# Run and stop on first failure
pytest tests/test_evaluator.py -x
```

Expected output when all tests pass:

```
tests/test_evaluator.py::TestF1::test_pass_doi_identifier PASSED
tests/test_evaluator.py::TestF1::test_pass_ark_identifier PASSED
...
tests/test_evaluator.py::TestDomainProfileIntegration::test_generic_profile_passes_where_domain_fails PASSED

52 passed in X.XXs
```

---

## Test file location

```
fair-assessment/
├── tests/
│   ├── __init__.py
│   └── test_evaluator.py    ← the test suite
├── app/
│   ├── models/
│   │   ├── profile.py
│   │   └── metadata.py
│   └── services/
│       └── evaluator.py     ← what is being tested
└── conftest.py              ← adds project root to Python path
```

---

## How tests are structured

Each test constructs a `NormalizedMetadata` object with known field values
and a `Profile` object with known configuration, calls the metric function
directly, and asserts the returned `MetricResult` status and evidence match
expectations. No database connection or network request is made.

```python
def test_pass_doi_identifier(self):
    meta = make_metadata(identifier="10.5281/zenodo.123456")
    profile = make_profile(accepted_identifiers=["doi"])
    result = check_f1(meta, profile)
    assert result.status == "pass"
    assert "doi" in result.evidence.lower()
```

Helper functions `make_metadata()` and `make_profile()` at the top of the
test file create objects with sensible defaults so each test only needs to
set the fields relevant to the scenario being tested.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'app'`**
Make sure you are running pytest from the project root, not from inside
the `tests/` folder. Also check that `conftest.py` exists in the project root.

```bash
# Correct
cd fair-assessment
pytest tests/test_evaluator.py -v

# Wrong
cd fair-assessment/tests
pytest test_evaluator.py -v
```

**`ImportError` for a specific module**
Run `pip install -r requirements.txt` to make sure all dependencies are
installed in your current environment.
