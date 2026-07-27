"""The generic (tool-agnostic) speaker-diarization adapter — cache-check, invoke the bound tool's pure-compute `diarize`, persist. Reused across every tool capability satisfying `SpeakerDiarizationToolProtocol`, exactly as `GenericVADAdapter` is reused across VAD tools."""

import os

from cjm_capability_primitives.speaker_diarization import SpeakerDiarizationResult, SpeakerTurn
from cjm_substrate.core.wire import get_call_envelope
from cjm_substrate.utils.hashing import hash_dict_canonical, hash_file

from .adapter import SpeakerDiarizationAdapter
from .storage import SpeakerDiarizationStorage


class GenericSpeakerDiarizationAdapter(SpeakerDiarizationAdapter):
    """Generic speaker-diarization adapter: cache-check -> pure-compute tool -> persist.

    Works against ANY tool satisfying `SpeakerDiarizationToolProtocol`. The
    bookends landed 2026-07-26 (the VAD-adapter precedent this class was born
    citing): full-source diarization costs ~46s/hour on cuda and sources run
    multi-hour, so re-runs are worth caching.

      1. cache check (file_path + file_hash + config_hash) BEFORE invoking the
         tool, so a hit never loads the pipeline;
      2. the tool's pure-compute `diarize` on a miss / forced call;
      3. `save_with_logging` (upsert by file_path + config_hash).

    Unlike VAD, `diarize` kwargs are NOT provenance pass-through: the
    speaker-count hints (num_speakers / min_speakers / max_speakers) steer the
    clustering, so they FOLD INTO `config_hash` — the same audio diarized
    under a different hint is a different cache row. `force` rides
    `CallEnvelope.control` (not a task kwarg, keeping `diarize(audio)` pure).
    Storage lives at `<CAPABILITY_DATA_DIR>/speaker_diarization.db`; the
    substrate injects the per-capability `CAPABILITY_DATA_DIR` at spawn.
    """

    # Per-call kwargs that change the clustering output — cache identity,
    # mirrored from the pyannote tool's diarize signature.
    HINT_KEYS = ("num_speakers", "min_speakers", "max_speakers")

    def _get_storage(self) -> SpeakerDiarizationStorage:
        """Lazily open the per-capability cache DB under the substrate-injected
        CAPABILITY_DATA_DIR (created at worker spawn)."""
        if getattr(self, "_storage", None) is None:
            db_path = os.path.join(os.environ["CAPABILITY_DATA_DIR"], "speaker_diarization.db")
            self._storage = SpeakerDiarizationStorage(db_path)
        return self._storage

    def diarize(
        self,
        audio: str,  # Path to the source audio to diarize (decoded PCM rendition)
        **kwargs,    # Speaker-count hints (cache identity) + provenance + tool options
    ) -> SpeakerDiarizationResult:  # Time-ordered anonymous speaker turns
        """Cache-check, invoke the bound tool's pure-compute `diarize`, persist."""
        file_path = str(audio)
        file_hash = hash_file(file_path)
        hints = {k: kwargs[k] for k in self.HINT_KEYS if kwargs.get(k) is not None}
        config_hash = hash_dict_canonical({**self.tool.get_current_config(), **hints})

        env = get_call_envelope()
        force = bool(env.control.get("force")) if env is not None else False

        storage = self._get_storage()
        if not force:
            cached = storage.get_cached(file_path, file_hash, config_hash)
            if cached is not None:
                return SpeakerDiarizationResult(
                    turns=[SpeakerTurn(**t) for t in (cached.turns or [])],
                    metadata=cached.metadata or {},
                )

        # Pure compute on the tool (cache miss / forced).
        result = self.tool.diarize(audio, **kwargs)

        # Persist. Content-addressed row; cache key is (file_path, config_hash)
        # with file_hash for content-correctness.
        storage.save_with_logging(
            file_path=file_path, file_hash=file_hash, config_hash=config_hash,
            turns=[t.to_dict() for t in result.turns], metadata=result.metadata,
        )
        return result
