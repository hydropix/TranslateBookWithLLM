"""
Script de test pour le systeme de checkpoint/reprise
"""
import sys
import os
import io

# Force UTF-8 encoding for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Ajouter le repertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.persistence.database import Database
from src.persistence.checkpoint_manager import CheckpointManager


def test_database_creation():
    """Test de création de la base de données"""
    print("=" * 60)
    print("Test 1: Création de la base de données")
    print("=" * 60)

    db = Database("translated_files/test_jobs.db")
    print("✅ Base de données créée avec succès")

    # Test création job
    success = db.create_job(
        translation_id="test_trans_001",
        file_type="txt",
        config={
            "source_language": "English",
            "target_language": "French",
            "model": "mistral-small:24b",
            "chunk_size": 25
        }
    )

    if success:
        print("✅ Job créé avec succès")
    else:
        print("❌ Échec de création du job")
        return False

    # Test récupération job
    job = db.get_job("test_trans_001")
    if job:
        print(f"✅ Job récupéré: {job['translation_id']}")
        print(f"   Type: {job['file_type']}")
        print(f"   Status: {job['status']}")
    else:
        print("❌ Job non trouvé")
        return False

    db.close()
    return True


def test_checkpoint_saving():
    """Test de sauvegarde de checkpoints"""
    print("\n" + "=" * 60)
    print("Test 2: Sauvegarde de checkpoints")
    print("=" * 60)

    manager = CheckpointManager("translated_files/test_jobs.db")

    # Simuler la sauvegarde de chunks
    for i in range(5):
        success = manager.save_checkpoint(
            translation_id="test_trans_001",
            chunk_index=i,
            original_text=f"Original text chunk {i}",
            translated_text=f"Texte traduit chunk {i}",
            chunk_data={
                "context_before": "",
                "main_content": f"Content {i}",
                "context_after": ""
            },
            translation_context={
                "last_llm_context": f"Context {i}"
            },
            total_chunks=10,
            completed_chunks=i + 1,
            failed_chunks=0
        )

        if success:
            print(f"✅ Checkpoint {i} sauvegardé")
        else:
            print(f"❌ Échec checkpoint {i}")
            return False

    return True


def test_checkpoint_loading():
    """Test de chargement de checkpoints"""
    print("\n" + "=" * 60)
    print("Test 3: Chargement de checkpoints")
    print("=" * 60)

    manager = CheckpointManager("translated_files/test_jobs.db")

    # Charger checkpoint
    checkpoint = manager.load_checkpoint("test_trans_001")

    if checkpoint:
        print("✅ Checkpoint chargé avec succès")
        print(f"   Resume from: chunk {checkpoint['resume_from_index']}")
        print(f"   Chunks sauvegardés: {len(checkpoint['chunks'])}")

        # Vérifier les chunks
        for chunk in checkpoint['chunks']:
            print(f"   - Chunk {chunk['chunk_index']}: {chunk['status']}")
    else:
        print("❌ Échec du chargement")
        return False

    return True


def test_resumable_jobs():
    """Test de la liste des jobs resumables"""
    print("\n" + "=" * 60)
    print("Test 4: Liste des jobs resumables")
    print("=" * 60)

    manager = CheckpointManager("translated_files/test_jobs.db")

    # Marquer comme pausé
    manager.mark_paused("test_trans_001")

    # Récupérer jobs resumables
    jobs = manager.get_resumable_jobs()

    if jobs:
        print(f"✅ {len(jobs)} job(s) resumable(s) trouvé(s)")
        for job in jobs:
            print(f"   - {job['translation_id']}: {job['file_type'].upper()}")
            print(f"     Progression: {job['progress_percentage']}%")
    else:
        print("❌ Aucun job resumable trouvé")
        return False

    return True


def test_cleanup():
    """Test de nettoyage"""
    print("\n" + "=" * 60)
    print("Test 5: Nettoyage")
    print("=" * 60)

    manager = CheckpointManager("translated_files/test_jobs.db")

    # Supprimer checkpoint
    success = manager.delete_checkpoint("test_trans_001")

    if success:
        print("✅ Checkpoint supprimé")
    else:
        print("❌ Échec de la suppression")
        return False

    # Vérifier suppression
    jobs = manager.get_resumable_jobs()
    if len(jobs) == 0:
        print("✅ Aucun job resumable (nettoyage confirmé)")
    else:
        print("❌ Des jobs existent encore")
        return False

    # Supprimer la base de test
    try:
        os.remove("translated_files/test_jobs.db")
        print("✅ Base de données de test supprimée")
    except Exception as e:
        print(f"⚠️  Impossible de supprimer la DB de test: {e}")

    return True


def main():
    """Exécuter tous les tests"""
    print("\n" + "TEST DU SYSTEME DE CHECKPOINT/REPRISE" + "\n")

    tests = [
        test_database_creation,
        test_checkpoint_saving,
        test_checkpoint_loading,
        test_resumable_jobs,
        test_cleanup
    ]

    results = []

    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ ERREUR: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    # Résumé
    print("\n" + "=" * 60)
    print("RÉSUMÉ DES TESTS")
    print("=" * 60)

    total = len(results)
    passed = sum(results)
    failed = total - passed

    print(f"Total: {total}")
    print(f"Reussis: {passed}")
    print(f"Echoues: {failed}")

    if failed == 0:
        print("\nTOUS LES TESTS SONT PASSES !")
        return 0
    else:
        print(f"\n{failed} TEST(S) ECHOUE(S)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
