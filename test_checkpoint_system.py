"""
Test script for the checkpoint/resume system
"""
import sys
import os
import io

# Force UTF-8 encoding for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.persistence.database import Database
from src.persistence.checkpoint_manager import CheckpointManager


def test_database_creation():
    """Test database creation"""
    print("=" * 60)
    print("Test 1: Database creation")
    print("=" * 60)

    db = Database("translated_files/test_jobs.db")
    print("✅ Database created successfully")

    # Test job creation
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
        print("✅ Job created successfully")
    else:
        print("❌ Job creation failed")
        return False

    # Test job retrieval
    job = db.get_job("test_trans_001")
    if job:
        print(f"✅ Job retrieved: {job['translation_id']}")
        print(f"   Type: {job['file_type']}")
        print(f"   Status: {job['status']}")
    else:
        print("❌ Job not found")
        return False

    db.close()
    return True


def test_checkpoint_saving():
    """Test checkpoint saving"""
    print("\n" + "=" * 60)
    print("Test 2: Checkpoint saving")
    print("=" * 60)

    manager = CheckpointManager("translated_files/test_jobs.db")

    # Simulate chunk saving
    for i in range(5):
        success = manager.save_checkpoint(
            translation_id="test_trans_001",
            chunk_index=i,
            original_text=f"Original text chunk {i}",
            translated_text=f"Translated text chunk {i}",
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
            print(f"✅ Checkpoint {i} saved")
        else:
            print(f"❌ Checkpoint {i} failed")
            return False

    return True


def test_checkpoint_loading():
    """Test checkpoint loading"""
    print("\n" + "=" * 60)
    print("Test 3: Checkpoint loading")
    print("=" * 60)

    manager = CheckpointManager("translated_files/test_jobs.db")

    # Load checkpoint
    checkpoint = manager.load_checkpoint("test_trans_001")

    if checkpoint:
        print("✅ Checkpoint loaded successfully")
        print(f"   Resume from: chunk {checkpoint['resume_from_index']}")
        print(f"   Saved chunks: {len(checkpoint['chunks'])}")

        # Verify chunks
        for chunk in checkpoint['chunks']:
            print(f"   - Chunk {chunk['chunk_index']}: {chunk['status']}")
    else:
        print("❌ Loading failed")
        return False

    return True


def test_resumable_jobs():
    """Test resumable jobs list"""
    print("\n" + "=" * 60)
    print("Test 4: Resumable jobs list")
    print("=" * 60)

    manager = CheckpointManager("translated_files/test_jobs.db")

    # Mark as paused
    manager.mark_paused("test_trans_001")

    # Get resumable jobs
    jobs = manager.get_resumable_jobs()

    if jobs:
        print(f"✅ {len(jobs)} resumable job(s) found")
        for job in jobs:
            print(f"   - {job['translation_id']}: {job['file_type'].upper()}")
            print(f"     Progress: {job['progress_percentage']}%")
    else:
        print("❌ No resumable jobs found")
        return False

    return True


def test_cleanup():
    """Test cleanup"""
    print("\n" + "=" * 60)
    print("Test 5: Cleanup")
    print("=" * 60)

    manager = CheckpointManager("translated_files/test_jobs.db")

    # Delete checkpoint
    success = manager.delete_checkpoint("test_trans_001")

    if success:
        print("✅ Checkpoint deleted")
    else:
        print("❌ Deletion failed")
        return False

    # Verify deletion
    jobs = manager.get_resumable_jobs()
    if len(jobs) == 0:
        print("✅ No resumable jobs (cleanup confirmed)")
    else:
        print("❌ Jobs still exist")
        return False

    # Delete test database
    try:
        os.remove("translated_files/test_jobs.db")
        print("✅ Test database deleted")
    except Exception as e:
        print(f"⚠️  Could not delete test DB: {e}")

    return True


def main():
    """Run all tests"""
    print("\n" + "CHECKPOINT/RESUME SYSTEM TEST" + "\n")

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
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    total = len(results)
    passed = sum(results)
    failed = total - passed

    print(f"Total: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if failed == 0:
        print("\nALL TESTS PASSED!")
        return 0
    else:
        print(f"\n{failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
