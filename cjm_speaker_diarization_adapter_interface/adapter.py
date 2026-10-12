"""The typed speaker-diarization task contract — the `SpeakerDiarizationAdapter` ABC + the `SpeakerDiarizationToolProtocol` structural contract (capability-unit Option C; session-D DECs 18d7de80 + d6df3a8e)."""

from abc import abstractmethod
from typing import Any, ClassVar, Dict, Protocol, runtime_checkable

from cjm_capability_primitives.speaker_diarization import SpeakerDiarizationResult
from cjm_substrate.core.adapter import TaskAdapter


# Canonical home (PILLAR 1c): the data noun lives in cjm-capability-primitives,
# so the tool capability depends on it, never on this adapter machinery.
# SCOPE (physical-speaker principle, DEC 44afb2df): this interface carries
# DIARIZATION only — audio in, ANONYMOUS time-ranged turns out. Mapping
# clusters to named identities is the correction TUI's assignment lane
# (human judgment); assignment semantics never enter this contract.


@runtime_checkable
class SpeakerDiarizationToolProtocol(Protocol):
    """Structural contract for speaker-diarization tool capabilities.

    `diarize` reads the original source audio (path) and returns time-ordered
    anonymous speaker turns in that audio's coordinates. `get_current_config`
    supplies the effective config whose canonical hash joins downstream
    identity/provenance composites."""

    def diarize(self, audio: str, **kwargs) -> SpeakerDiarizationResult: ...
    def get_current_config(self) -> Dict[str, Any]: ...


class SpeakerDiarizationAdapter(TaskAdapter):
    """Typed speaker-diarization task adapter: source audio path in,
    `SpeakerDiarizationResult` (anonymous time-ranged turns) out.

    Input contract: the caller passes a path to the audio whose COORDINATES it
    needs preserved — turn times always index into exactly that audio (a tool
    that resamples internally must report source-coordinate times). Cluster
    labels are result-scoped only.

    Speaker-count hints ride kwargs (`num_speakers`, `min_speakers`,
    `max_speakers`) — optional, tool-interpreted; a tool without count control
    ignores them.

    No cache/persist bookends in v0: the transcription workflow persists
    results on its own run manifests (turns ride BESIDE transcripts,
    a9cadfec), and diarization runs once per source per config — a cache DB
    can land in a generic-adapter revision if re-run pressure appears.

    Implementations run in-worker beside their tool capability and are
    constructed with the bound tool instance: `AdapterClass(tool)`. The result
    DTO is wire-registered ("speaker_diarization.result"): returned values
    cross the worker boundary typed.
    """

    task_name: ClassVar[str] = "speaker_diarization"
    required_tool_protocol: ClassVar[type] = SpeakerDiarizationToolProtocol

    def __init__(
        self,
        tool: SpeakerDiarizationToolProtocol,  # The bound tool capability instance (worker-side binding)
    ):
        self.tool = tool

    @abstractmethod
    def diarize(
        self,
        audio: str,  # Path to the source audio to diarize (turn times index into THIS audio)
        **kwargs,    # Speaker-count hints + provenance + tool options
    ) -> SpeakerDiarizationResult:  # Time-ordered anonymous speaker turns
        """Diarize audio into time-ordered anonymous speaker turns."""
        ...
