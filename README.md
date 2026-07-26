# cjm-speaker-diarization-adapter-interface

Typed speaker-diarization task-adapter interface for the
[cjm-substrate](https://github.com/cj-mills/cjm-substrate) runtime:

- **`SpeakerDiarizationToolProtocol`** — structural contract for diarization
  tool capabilities: `diarize(audio, **kwargs) -> SpeakerDiarizationResult`
  + `get_current_config()`.
- **`SpeakerDiarizationAdapter`** — the task-adapter ABC
  (`task_name = "speaker_diarization"`).
- **`GenericSpeakerDiarizationAdapter`** — thin tool-agnostic pass-through,
  reused by any conforming tool capability (e.g.
  [cjm-capability-pyannote](https://github.com/cj-mills/cjm-capability-pyannote)).

The `SpeakerDiarizationResult` / `SpeakerTurn` data nouns live in
[cjm-capability-primitives](https://github.com/cj-mills/cjm-capability-primitives)
and are wire-registered (`speaker_diarization.result`), so results cross the
worker boundary typed.

**Scope**: diarization only — audio in, *anonymous* time-ranged speaker turns
out. Turn times index into the caller's original audio; cluster labels
(`SPEAKER_00`, …) are result-scoped. Mapping clusters to named identities is
downstream human judgment (the correction TUI's assignment lane), never this
interface's job.

## Install

```bash
pip install cjm-speaker-diarization-adapter-interface
```
