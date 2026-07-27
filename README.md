# cjm-speaker-diarization-adapter-interface

<!-- generated from the context graph by `cjm-context-graph readme` — do not edit by hand; edit the graph (the urge to hand-edit = move it on-graph) -->

Adapter interface for speaker-diarization capabilities — the speaker_diarization task-channel contract (audio → typed SpeakerTurn/SpeakerDiarizationResult) that capability libs implement and workflow cores consume; the generic adapter owns the SQLite cache bookends (content-addressed, speaker-count hints fold into the config hash).

## Modules

- **`cjm_speaker_diarization_adapter_interface.__init__`**
- **`cjm_speaker_diarization_adapter_interface.adapter`** — The typed speaker-diarization task contract — the `SpeakerDiarizationAdapter` ABC + the `SpeakerDiarizationToolProtocol` structural contract (capability-unit Option C; session-D DECs 18d7de80 + d6df3a8e).
- **`cjm_speaker_diarization_adapter_interface.generic`** — The generic (tool-agnostic) speaker-diarization adapter — cache-check, invoke the bound tool's pure-compute `diarize`, persist. Reused across every tool capability satisfying `SpeakerDiarizationToolProtocol`, exactly as `GenericVADAdapter` is reused across VAD tools.
- **`cjm_speaker_diarization_adapter_interface.storage`** — Standardized SQLite storage for speaker-diarization results with content hashing.

## API

### `cjm_speaker_diarization_adapter_interface.adapter`

- `SpeakerDiarizationAdapter` _class_ — Typed speaker-diarization task adapter: source audio path in,
- `SpeakerDiarizationToolProtocol` _class_ — Structural contract for speaker-diarization tool capabilities.

### `cjm_speaker_diarization_adapter_interface.generic`

- `GenericSpeakerDiarizationAdapter` _class_ — Generic speaker-diarization adapter: cache-check -> pure-compute tool -> persist.

### `cjm_speaker_diarization_adapter_interface.storage`

- `SpeakerDiarizationRow` _class_ — A single row from the speaker_diarization_results table.
- `SpeakerDiarizationStorage` _class_ — Standardized SQLite storage for speaker-diarization results.

## Dependencies

**Depends on:** `cjm-capability-primitives`, `cjm-substrate`
**Used by:** `cjm-capability-pyannote`
