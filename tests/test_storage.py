"""Tests for the speaker-diarization storage layer — content-correct cache semantics on the VAD-adapter precedent."""

from cjm_speaker_diarization_adapter_interface.storage import (SpeakerDiarizationRow,
                                                               SpeakerDiarizationStorage)
from cjm_substrate.utils.hashing import hash_file


def _seeded_storage(tmp_path):
    """Storage with one saved result for a real (tiny) audio file."""
    storage = SpeakerDiarizationStorage(str(tmp_path / "speaker_diarization.db"))
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"pcm-one")
    turns = [{"start": 0.2, "end": 1.5, "speaker": "SPEAKER_00", "confidence": None},
             {"start": 1.8, "end": 3.9, "speaker": "SPEAKER_01", "confidence": 0.9}]
    storage.save(file_path=str(audio), file_hash="sha256:aaa", config_hash="cfg1",
                 turns=turns, metadata={"speaker_count": 2})
    return storage, str(audio), turns


def test_save_get_cached_and_content_correctness(tmp_path):
    storage, audio, turns = _seeded_storage(tmp_path)
    row = storage.get_cached(audio, "sha256:aaa", "cfg1")
    assert isinstance(row, SpeakerDiarizationRow)
    assert row.turns == turns
    assert row.metadata == {"speaker_count": 2}
    assert row.created_at is not None
    # changed content (new file_hash) misses even though a row exists at
    # the same (file_path, config_hash)
    assert storage.get_cached(audio, "sha256:bbb", "cfg1") is None
    # unknown config misses
    assert storage.get_cached(audio, "sha256:aaa", "cfg2") is None


def test_insert_or_replace_on_cache_key(tmp_path):
    storage, audio, _ = _seeded_storage(tmp_path)
    storage.save(file_path=audio, file_hash="sha256:bbb", config_hash="cfg1",
                 turns=[{"start": 0.0, "end": 9.9, "speaker": "SPEAKER_00",
                         "confidence": None}])
    # upsert replaced the (file_path, cfg1) row — no duplicate
    assert len(storage.list_jobs()) == 1
    assert storage.get_cached(audio, "sha256:aaa", "cfg1") is None
    row = storage.get_cached(audio, "sha256:bbb", "cfg1")
    assert row.turns[0]["end"] == 9.9
    assert row.metadata is None


def test_save_with_logging_success_and_swallowed_failure(tmp_path):
    storage, audio, turns = _seeded_storage(tmp_path)
    assert storage.save_with_logging(file_path=audio, file_hash="sha256:aaa",
                                     config_hash="cfg2", turns=turns) is True

    def _boom(*args, **kwargs):
        raise RuntimeError("disk full")

    storage.save = _boom  # instance attribute shadows the method
    assert storage.save_with_logging(file_path=audio, file_hash="x",
                                     config_hash="cfg3") is False


def test_list_jobs_and_verify_file(tmp_path):
    storage, audio, _ = _seeded_storage(tmp_path)
    storage.save(file_path=audio, file_hash="h", config_hash="cfg2")
    rows = storage.list_jobs()
    assert len(rows) == 2
    assert rows[0].created_at >= rows[1].created_at  # newest first
    # verify_file compares the stored hash against the file's REAL hash
    storage.save(file_path=audio, file_hash=hash_file(audio),
                 config_hash="cfg-real")
    assert storage.verify_file(audio, "cfg-real") is True
    assert storage.verify_file(audio, "cfg1") is False  # seeded fake hash
    assert storage.verify_file(audio, "nope") is None
