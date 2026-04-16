"""
Tests for the new features: No-Index Zones, Version Awareness, Drift Detection.

Run with: python3 -m pytest tests/test_new_features.py -v
Or standalone: python3 tests/test_new_features.py
"""
import sys
import os

# Add backend to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── 1. Version Awareness — _detect_doc_status() ─────────────────────────────

def test_detect_draft_in_title():
    from app.services.drive_ingestion import _detect_doc_status
    assert _detect_doc_status("DRAFT - Product Roadmap Q3", "Some content here", {}) == "draft"
    assert _detect_doc_status("[DRAFT] API Design Doc", "Normal content", {}) == "draft"
    assert _detect_doc_status("WIP pricing model", "Final numbers", {}) == "draft"

def test_detect_draft_in_content():
    from app.services.drive_ingestion import _detect_doc_status
    assert _detect_doc_status("Product Roadmap", "This is a draft document, do not share externally", {}) == "draft"
    assert _detect_doc_status("Notes", "Work in progress — needs review from team leads", {}) == "draft"

def test_detect_in_review():
    from app.services.drive_ingestion import _detect_doc_status
    assert _detect_doc_status("RFC - New Auth Flow", "Proposed approach for auth", {}) == "in_review"
    assert _detect_doc_status("API Spec [REVIEW]", "Please review this spec", {}) == "in_review"
    assert _detect_doc_status("Design Doc", "This document is pending review by the team", {}) == "in_review"

def test_detect_finalized():
    from app.services.drive_ingestion import _detect_doc_status
    assert _detect_doc_status("Product Roadmap Q3 2026", "Final approved roadmap for Q3", {}) == "finalized"
    assert _detect_doc_status("Meeting Notes 15/03/2026", "Attendees discussed the timeline", {}) == "finalized"

def test_draft_takes_priority_over_review():
    """If both draft and review signals exist, draft wins (checked first)."""
    from app.services.drive_ingestion import _detect_doc_status
    assert _detect_doc_status("DRAFT for review", "Content here", {}) == "draft"


# ── 2. No-Index Zones — exclusion_service logic ─────────────────────────────

def test_exclusion_cache_logic():
    """Test the in-memory cache without hitting the DB."""
    from app.services import exclusion_service

    # Manually set the cache to simulate loaded rules
    exclusion_service._cache = {
        "slack": {"C_HR_CHANNEL", "C_SALARY"},
        "drive": {"folder_confidential_123"},
        "clickup": {"space_mna_456"},
    }

    assert exclusion_service.is_excluded("slack", "C_HR_CHANNEL") is True
    assert exclusion_service.is_excluded("slack", "C_GENERAL") is False
    assert exclusion_service.is_excluded("drive", "folder_confidential_123") is True
    assert exclusion_service.is_excluded("drive", "folder_public_789") is False
    assert exclusion_service.is_excluded("clickup", "space_mna_456") is True
    assert exclusion_service.is_excluded("clickup", "space_eng_001") is False
    # Unknown source type
    assert exclusion_service.is_excluded("gmail", "anything") is False

    assert exclusion_service.get_excluded_ids("slack") == {"C_HR_CHANNEL", "C_SALARY"}
    assert exclusion_service.get_excluded_ids("gmail") == set()

    # Clean up
    exclusion_service._cache = {}


# ── 3. Drift Detection — cosine similarity ───────────────────────────────────

def test_cosine_similarity():
    from app.services.drift_detector import _cosine_similarity

    # Identical vectors → 1.0
    assert abs(_cosine_similarity([1, 0, 0], [1, 0, 0]) - 1.0) < 0.001

    # Orthogonal vectors → 0.0
    assert abs(_cosine_similarity([1, 0, 0], [0, 1, 0]) - 0.0) < 0.001

    # Opposite vectors → -1.0
    assert abs(_cosine_similarity([1, 0, 0], [-1, 0, 0]) - (-1.0)) < 0.001

    # Zero vectors → 0.0
    assert _cosine_similarity([0, 0, 0], [1, 2, 3]) == 0.0

    # Similar vectors → high score
    sim = _cosine_similarity([1, 2, 3], [1.1, 2.1, 3.1])
    assert sim > 0.99


# ── 4. Model fields exist ────────────────────────────────────────────────────

def test_exclusion_rule_model():
    from app.models import ExclusionRule
    assert ExclusionRule.__tablename__ == "exclusion_rules"
    assert hasattr(ExclusionRule, "source_type")
    assert hasattr(ExclusionRule, "identifier")
    assert hasattr(ExclusionRule, "name")
    assert hasattr(ExclusionRule, "reason")

def test_document_doc_status_field():
    from app.models import Document
    assert hasattr(Document, "doc_status")


# ── 5. Drift detector result structure ────────────────────────────────────────

def test_drift_result_defaults():
    from app.services.drift_detector import DriftResult
    result = DriftResult()
    assert result.has_drift is False
    assert result.alert_text == ""
    assert result.matches == []


# ── Run all tests ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import traceback

    tests = [
        test_detect_draft_in_title,
        test_detect_draft_in_content,
        test_detect_in_review,
        test_detect_finalized,
        test_draft_takes_priority_over_review,
        test_exclusion_cache_logic,
        test_cosine_similarity,
        test_exclusion_rule_model,
        test_document_doc_status_field,
        test_drift_result_defaults,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {test.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    if failed > 0:
        sys.exit(1)
