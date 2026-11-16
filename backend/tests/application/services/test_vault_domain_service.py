"""
Unit tests for VaultDomainService (TDD).
Spec: obsidian_vault/docs/features/feature_dynamic_knowledge_domains.md
"""
from pathlib import Path
import pytest

from src.application.services.vault_domain_service import VaultDomainService, KnowledgeDomain


@pytest.fixture
def mock_vault(tmp_path: Path) -> Path:
    """Creates a mock vault structure with core domains and HOME.md."""
    vault = tmp_path / "mock_vault"
    vault.mkdir()

    # Create HOME.md
    home_file = vault / "HOME.md"
    home_file.write_text("# HOME Master Index\n\n## Dominios\n", encoding="utf-8")

    # Create core domains
    (vault / "00_meta_project").mkdir()
    (vault / "00_meta_project" / "MOC_Project_TFM.md").write_text("# MOC Project", encoding="utf-8")
    (vault / "00_meta_project" / "doc1.md").write_text("# Doc 1", encoding="utf-8")

    (vault / "01_enterprise_architecture").mkdir()
    (vault / "01_enterprise_architecture" / "MOC_Enterprise_Architecture.md").write_text("# MOC Ent", encoding="utf-8")

    (vault / "learned").mkdir()
    (vault / "learned" / "MOC_Learned_Knowledge.md").write_text("# MOC Learned", encoding="utf-8")
    (vault / "learned" / "doc_learned.md").write_text("# Learned doc", encoding="utf-8")

    (vault / "deliberations").mkdir()
    (vault / "deliberations" / "MOC_Deliberations.md").write_text("# MOC Deliberations", encoding="utf-8")

    # Hidden folder should be ignored
    (vault / ".obsidian").mkdir()
    (vault / ".obsidian" / "config.json").write_text("{}", encoding="utf-8")

    return vault


def test_list_domains_returns_all_core_domains_with_correct_counts(mock_vault: Path) -> None:
    domains = VaultDomainService.list_domains(mock_vault)

    domain_ids = [d.id for d in domains]
    assert "00_meta_project" in domain_ids
    assert "01_enterprise_architecture" in domain_ids
    assert "learned" in domain_ids
    assert "deliberations" in domain_ids

    # Check document counts
    meta_dom = next(d for d in domains if d.id == "00_meta_project")
    assert meta_dom.document_count == 2  # MOC + doc1.md
    assert meta_dom.is_system is True

    learned_dom = next(d for d in domains if d.id == "learned")
    assert learned_dom.document_count == 2


def test_create_domain_creates_directory_moc_and_updates_home(mock_vault: Path) -> None:
    new_domain = VaultDomainService.create_domain(
        vault_root=mock_vault,
        domain_id="04_data_ai_platform",
        name="Plataforma de Datos e IA",
        description="Directrices y arquitecturas de datos",
    )

    assert isinstance(new_domain, KnowledgeDomain)
    assert new_domain.id == "04_data_ai_platform"
    assert new_domain.name == "Plataforma de Datos e IA"
    assert (mock_vault / "04_data_ai_platform").is_dir()

    # MOC file should exist
    moc_path = mock_vault / new_domain.moc_file
    assert moc_path.exists()
    moc_content = moc_path.read_text(encoding="utf-8")
    assert "Plataforma de Datos e IA" in moc_content
    assert "type: moc" in moc_content

    # HOME.md should be updated with a link to the new MOC
    home_content = (mock_vault / "HOME.md").read_text(encoding="utf-8")
    assert "04_data_ai_platform" in home_content


def test_create_domain_invalid_id_raises_value_error(mock_vault: Path) -> None:
    with pytest.raises(ValueError, match="Invalid domain ID"):
        VaultDomainService.create_domain(
            vault_root=mock_vault,
            domain_id="../hack_dir",
            name="Insecure Domain",
        )

