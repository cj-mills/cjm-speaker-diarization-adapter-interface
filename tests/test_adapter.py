"""Tests for the speaker-diarization adapter interface — protocol conformance + the generic pass-through."""
from typing import Any, Dict

from cjm_capability_primitives.speaker_diarization import (SpeakerDiarizationResult,
                                                           SpeakerTurn)
from cjm_speaker_diarization_adapter_interface.adapter import (
    SpeakerDiarizationAdapter, SpeakerDiarizationToolProtocol)
from cjm_speaker_diarization_adapter_interface.generic import (
    GenericSpeakerDiarizationAdapter)


class FakeDiarizerTool:
    """Minimal tool satisfying the structural protocol: two fixed turns,
    honoring a num_speakers=1 hint by merging them."""

    def __init__(self):
        self.calls = 0
        self.last_kwargs: Dict[str, Any] = {}

    def diarize(self, audio: str, **kwargs) -> SpeakerDiarizationResult:
        self.calls += 1
        self.last_kwargs = dict(kwargs)
        if kwargs.get("num_speakers") == 1:
            turns = [SpeakerTurn(start=0.2, end=3.9, speaker="SPEAKER_00")]
        else:
            turns = [SpeakerTurn(start=0.2, end=1.5, speaker="SPEAKER_00"),
                     SpeakerTurn(start=1.8, end=3.9, speaker="SPEAKER_01")]
        return SpeakerDiarizationResult(
            turns=turns, metadata={"speaker_count": len({t.speaker for t in turns}),
                                   "audio": audio})

    def get_current_config(self) -> Dict[str, Any]:
        return {"model_id": "fake-diarizer"}


def test_fake_tool_satisfies_protocol():
    assert isinstance(FakeDiarizerTool(), SpeakerDiarizationToolProtocol)


def test_adapter_declares_task_contract():
    assert SpeakerDiarizationAdapter.task_name == "speaker_diarization"
    assert (SpeakerDiarizationAdapter.required_tool_protocol
            is SpeakerDiarizationToolProtocol)


def test_generic_adapter_passes_through_with_hints():
    tool = FakeDiarizerTool()
    adapter = GenericSpeakerDiarizationAdapter(tool)
    result = adapter.diarize("/audio/source.mp3")
    assert tool.calls == 1
    assert [t.speaker for t in result.turns] == ["SPEAKER_00", "SPEAKER_01"]
    assert result.metadata["audio"] == "/audio/source.mp3"
    # speaker-count hints ride kwargs untouched
    hinted = adapter.diarize("/audio/source.mp3", num_speakers=1)
    assert tool.last_kwargs == {"num_speakers": 1}
    assert len(hinted.turns) == 1 and hinted.metadata["speaker_count"] == 1
