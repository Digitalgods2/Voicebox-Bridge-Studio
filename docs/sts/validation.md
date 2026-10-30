# Privacy-safe validation record

Last updated: 2026-08-11

This repository records functional outcomes without publishing host paths, Windows usernames, hardware fingerprints, cloned-profile names, source-media names, job identifiers, or raw benchmark manifests. Detailed performance measurements remain local runtime data.

## Engine and model integrity

- OpenVoice source and model revisions are pinned in `config/openvoice-v2.provenance.json`.
- The worker rejects PyTorch versions below 2.13.0 and verifies the converter checkpoint against the tracked SHA-256 before deserialization.
- The converter checkpoint is loaded with `weights_only=True` and checked for missing or unexpected state keys.
- Model loading, CUDA synchronization, and peak-memory collection complete through the isolated worker.
- After the PyTorch 2.13.0/CUDA 12.6 security upgrade, a real CUDA model probe and short speech conversion completed; the output passed FFprobe inspection and a complete FFmpeg error-on-decode pass.
- Runtime inference uses local files and does not require a cloud API.

## Audio conversion

- A representative authorized recording completed the full local-audio conversion path.
- The published WAV passed FFprobe inspection and a complete FFmpeg error-on-decode pass.
- One model load can process multiple chunks while durable progress state is updated between chunks.
- Pitch and tone processing preserve the intended sample rate and exact frame count.

## Timeline reconstruction and video remux

- Imported videos are streamed atomically to an isolated UUID-addressed directory and are resolved by upload ID rather than a caller-provided filesystem path.
- The imported-video path does not invoke the downloader or mutate the single-entry YouTube source cache.
- Imported and downloaded sources use the same audio extraction, chunk conversion, reconstruction, post-processing, remux, and output-validation implementation.
- Multi-chunk reconstruction produced exactly the extracted source-audio frame count.
- Chunk overlaps are trimmed before placement, preventing cumulative timeline drift.
- The original video stream is copied without re-encoding.
- The default converted-video output stores audio as lossless FLAC in Matroska; the optional MP4 output stores audio as AAC for broader compatibility.
- Completed output passes full audio/video decode validation before a job is marked successful.

## Local-only quality review

Subjective voice-identity, intelligibility, pacing, emphasis, and emotional-performance observations are intentionally kept outside source control because they can reveal local voice-profile and source-media details.

## Built-in integration (2026-10-30)

After STS moved into the merged application:

- The STS test suite (80 tests) passes without torch or a GPU, including in-place workspace-sample resolution, sample/profile ownership checks, size limits, and the `/sts` job API.
- An imported workspace library was listed through `/sts/voices` with sample counts, and references resolved in place inside the workspace data directory without copies.
- One profile's own reference sample was converted into another workspace profile's voice through `POST /sts/audio/jobs` on local CUDA hardware. The output WAV fully decoded, was audible, and matched the source duration exactly.
- Frontend typecheck, lint, and the production web build pass with the Voice Changer tab.
