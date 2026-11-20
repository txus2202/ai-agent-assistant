"""
Unit tests for SearchFilter with multi-category and multi-value support (TDD).
Spec: obsidian_vault/docs/features/feature_dynamic_knowledge_domains.md (AC 6)
"""
from src.domain.value_objects.document_chunk import SearchFilter


def test_search_filter_scalar_fields():
    f = SearchFilter(type="adr", category="enterprise", status="implemented")
    assert f.type == "adr"
    assert f.category == "enterprise"
    assert f.status == "implemented"
    assert hash(f) is not None


def test_search_filter_list_fields_converted_to_tuple_and_hashable():
    f = SearchFilter(
        type=["adr", "standard"],
        category=["enterprise", "external-learning"],
        domain=["01_enterprise_architecture", "learned"],
    )
    assert isinstance(f.type, tuple)
    assert f.type == ("adr", "standard")
    assert isinstance(f.category, tuple)
    assert f.category == ("enterprise", "external-learning")
    assert isinstance(f.domain, tuple)
    assert f.domain == ("01_enterprise_architecture", "learned")
    assert hash(f) is not None


def test_search_filter_tuple_fields_preserved():
    f = SearchFilter(category=("enterprise", "deliberation"))
    assert f.category == ("enterprise", "deliberation")
    assert hash(f) is not None

