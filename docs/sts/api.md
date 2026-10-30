# Speech-to-speech API

Speech-to-speech (STS) is built into the app's backend alongside TTS. When the
app is running, the STS endpoints are under `/sts` at `http://127.0.0.1:17493`.
Interactive documentation is at `/docs` (the **Speech-to-Speech** section), and
the machine-readable schema is at `/openapi.json`.

STS reads voice profiles and their reference samples directly from the
workspace database, the same profiles the Voices tab and TTS use. There is no
separate service to start and no reference download.

## Upload, select a voice, download

| Method and path | Purpose |
| --- | --- |
| `GET /sts/voices` | List workspace voice profiles with `sample_count`; use a profile's `id` as `profile_id` |
| `GET /sts/voices/{profile_id}` | Retrieve one profile |
| `GET /sts/voices/{profile_id}/samples` | List reference samples, their IDs, and `audio_url` |
| `POST /sts/speech` | Upload raw speech bytes and start a background conversion |
| `GET /sts/audio/jobs/{job_id}` | Read status, selected voice, options, and errors |
| `GET /sts/audio/jobs/{job_id}/audio` | Download the completed WAV |
| `GET /sts/audio/jobs?limit=50&offset=0` | List audio jobs, newest first |
| `GET /sts/status` | Feature flags plus engine, video-tool, and YouTube readiness |
| `GET /sts/engine/status` | Inspect the isolated engine without loading the model |
| `POST /sts/engine/probe` | Load the model once and report device readiness |

`POST /sts/speech` takes query parameters `filename`, `profile_id`, and
`authorized=true` (confirmation that you have permission to use both media and
voice). Send the file itself as the request body, **not multipart/form-data**.
Use `Content-Type: application/octet-stream`. Audio uploads are capped at 1 GiB;
accepted extensions are WAV, MP3, FLAC, M4A, AAC, OGG, OPUS, and WMA.
The conversion engine must be able to decode the contents.

Optional parameters:

- `sample_id`: automatically selected only when the profile has exactly one
  sample. Multiple samples require an explicit choice. Preset and designed
  profiles have no reference samples and cannot be used for STS.
- `tau`: conversion parameter, 0–1, default 0.3.
- `pitch_semitones` and `brightness_db`: default 0; see `/docs` for allowed ranges.

The response is HTTP **202**, with `Location` pointing to `status_url` and
`Retry-After: 2`. Poll every two seconds until `status` is `completed` or `failed`.
`download_url` is null until completion. Failed jobs include an `error` object.
Downloading an unfinished or failed job returns **409**; unknown IDs return
**404**; invalid parameters or unusable voices return **422**. Failures after
acceptance appear in the job record.

## Runnable Python client

The example uses only Python's standard library and streams uploads/downloads:

```powershell
python examples/speech_client.py
python examples/speech_client.py --input speech.wav --voice PROFILE_UUID --authorized --output converted.wav
```

To send bytes directly with curl on Windows:

```powershell
curl.exe "http://127.0.0.1:17493/sts/voices"
curl.exe -X POST "http://127.0.0.1:17493/sts/speech?filename=speech.wav&profile_id=PROFILE_UUID&authorized=true" -H "Content-Type: application/octet-stream" --data-binary "@speech.wav"
```

## Delete uploads and results

| Method and path | Removes |
| --- | --- |
| `DELETE /sts/inputs/{input_id}` | An uploaded audio file and its metadata |
| `DELETE /sts/video-inputs/{video_input_id}` | An imported video and its metadata |
| `DELETE /sts/audio/jobs/{job_id}` | A finished audio job's record and converted WAV |
| `DELETE /sts/video/jobs/{job_id}` (or `/sts/youtube/jobs/{job_id}`) | A finished video job's folder, including its output video |

Each returns `{"deleted": true}`. Unknown IDs return **404** and malformed IDs
**422**. An upload or job that a queued or running job still needs returns
**409**; wait for the job to finish. Deleting a YouTube job keeps the cached
source video; clear it separately with `DELETE /sts/youtube/cache`.

## Reuse uploads and other workflows

Upload once with `POST /sts/inputs?filename=speech.wav` (raw bytes), then submit
`POST /sts/audio/jobs` with JSON:

```json
{"input_id":"UPLOAD_UUID","profile_id":"PROFILE_UUID","authorized":true,"pitch_semitones":0,"brightness_db":0}
```

Repeat with different voices using the same input ID. `POST /sts/conversions`
converts synchronously and returns the completed manifest. Local-video uploads
(`POST /sts/video-inputs`, `POST /sts/video/jobs`, `GET /sts/video/jobs/{id}`)
and YouTube jobs (`POST /sts/youtube/jobs`, `GET /sts/youtube/jobs/{id}`,
`GET`/`DELETE /sts/youtube/cache`) are also described in `/docs`. Media is
served with byte-range support under `/sts/media/...`.

Video jobs accept `output_format` as `mkv` (the default, with lossless FLAC
audio) or `mp4` (with AAC audio for broader compatibility). In both formats
the source video stream is copied without re-encoding. MKV carries source
subtitle streams when available; MP4 output omits them.

## Command line

The same workspace is available without the server:

```powershell
backend\venv\Scripts\python -m backend.sts --data-dir data profiles
backend\venv\Scripts\python -m backend.sts --data-dir data samples PROFILE_UUID
backend\venv\Scripts\python -m backend.sts --data-dir data convert speech.wav PROFILE_UUID SAMPLE_UUID --output converted.wav
backend\venv\Scripts\python -m backend.sts engine-status
```

## Execution and storage

Inference stays local and runs one conversion at a time on a shared lock. Run
one server process per data directory. STS uploads, jobs, and outputs live in
the workspace data directory next to the voice library (`inputs/`, `outputs/`,
`jobs/`, `audio_jobs/`, `video_inputs/`, `video_jobs/`, `youtube_cache/`).
Jobs and outputs survive restart; queued/running audio jobs become failed with
an `Interrupted` error on startup and must be submitted again. Submission is
not idempotent: retrying a POST creates another job. There is no cancellation
or automatic retry.

Keep the unauthenticated API on loopback. At startup, the server performs
manifest-driven cleanup of video-job intermediates and stale terminal jobs.
Completed video jobs are retained for 30 days by default; failed jobs are
retained for 24 hours for diagnostics. Override these periods with the
`STS_VIDEO_JOB_RETENTION_DAYS`, `STS_FAILED_VIDEO_JOB_RETENTION_HOURS`, and
`STS_ORPHAN_VIDEO_INPUT_RETENTION_HOURS` environment variables (the older
`BRIDGE_*` names are still accepted). Set `STS_ENGINE_DEVICE` to `cpu`,
`cuda`, or `cuda:<index>`, and `STS_ENGINE_ROOT` if the isolated engine lives
outside the project folder. Invalid manifests are preserved. Benchmark short
speech before large inputs; the audio endpoint converts in one pass, while the
video workflow provides chunked conversion.
