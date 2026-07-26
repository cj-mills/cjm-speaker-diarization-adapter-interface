"""The generic (tool-agnostic) speaker-diarization adapter — a thin typed pass-through to the bound tool's `diarize`. Reused across every tool capability satisfying `SpeakerDiarizationToolProtocol`, exactly as `GenericVADAdapter` is reused across VAD tools."""

from cjm_capability_primitives.speaker_diarization import SpeakerDiarizationResult

from .adapter import SpeakerDiarizationAdapter


class GenericSpeakerDiarizationAdapter(SpeakerDiarizationAdapter):
    """Generic speaker-diarization adapter: invoke the bound tool.

    Works against ANY tool satisfying `SpeakerDiarizationToolProtocol`.
    Deliberately bookend-free in v0 (no cache DB, no force control): the
    transcription workflow persists turns on its run manifests, and
    diarization runs once per source per config. If re-run pressure ever
    makes caching worthwhile, the bookends land here without touching any
    tool (the VAD-adapter precedent).
    """

    def diarize(
        self,
        audio: str,  # Path to the source audio to diarize
        **kwargs,    # Speaker-count hints + provenance + tool options
    ) -> SpeakerDiarizationResult:  # Time-ordered anonymous speaker turns
        """Invoke the bound tool's `diarize`."""
        return self.tool.diarize(audio, **kwargs)
