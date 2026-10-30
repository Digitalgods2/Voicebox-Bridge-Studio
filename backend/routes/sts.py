"""Speech-to-speech (voice changer) endpoints.

STS is a built-in feature alongside TTS: it converts uploaded audio, local
videos, and authorized YouTube videos into a workspace voice profile using
the isolated OpenVoice V2 runtime, while preserving the source's timing.
"""

from __future__ import annotations

import logging
import mimetypes
import threading
from datetime import timedelta
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from ..sts.audio_effects import MAX_BRIGHTNESS_DB, MAX_PITCH_SEMITONES, AudioEffectsError
from ..sts.audio_jobs import AudioJobs
from ..sts.conversion_service import ConversionService
from ..sts.media_store import MediaInUseError, MediaStore
from ..sts.openvoice_engine import OpenVoiceEngine, OpenVoiceError
from ..sts.settings import STSSettings
from ..sts.storage_cleanup import StorageCleanup
from ..sts.workspace_voices import VoiceWorkspaceError, WorkspaceVoices
from ..sts.youtube_service import YouTubeJobError, YouTubeJobService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sts", tags=["Speech-to-Speech"])

STS_FEATURES = [
    "audio-adjustments-v1",
    "youtube-source-cache-v1",
    "local-video-upload-v1",
    "video-output-formats-v1",
    "secure-openvoice-runtime-v1",
    "workspace-voices-v1",
]


class ConversionRequest(BaseModel):
    input_id: str
    profile_id: str
    sample_id: str
    tau: float = Field(default=0.3, ge=0.0, le=1.0)
    pitch_semitones: float = Field(default=0.0, ge=-MAX_PITCH_SEMITONES, le=MAX_PITCH_SEMITONES)
    brightness_db: float = Field(default=0.0, ge=-MAX_BRIGHTNESS_DB, le=MAX_BRIGHTNESS_DB)


class YouTubeJobRequest(BaseModel):
    youtube_url: str = Field(min_length=1, max_length=2048)
    profile_id: str
    sample_id: str
    tau: float = Field(default=0.3, ge=0.0, le=1.0)
    pitch_semitones: float = Field(default=0.0, ge=-MAX_PITCH_SEMITONES, le=MAX_PITCH_SEMITONES)
    brightness_db: float = Field(default=0.0, ge=-MAX_BRIGHTNESS_DB, le=MAX_BRIGHTNESS_DB)
    output_format: Literal["mkv", "mp4"] = "mkv"
    authorized: bool = False


class AudioJobRequest(ConversionRequest):
    input_id: UUID
    profile_id: UUID
    sample_id: UUID | None = None
    authorized: bool = False


class LocalVideoJobRequest(BaseModel):
    video_input_id: str
    profile_id: str
    sample_id: str
    tau: float = Field(default=0.3, ge=0.0, le=1.0)
    pitch_semitones: float = Field(default=0.0, ge=-MAX_PITCH_SEMITONES, le=MAX_PITCH_SEMITONES)
    brightness_db: float = Field(default=0.0, ge=-MAX_BRIGHTNESS_DB, le=MAX_BRIGHTNESS_DB)
    output_format: Literal["mkv", "mp4"] = "mkv"
    authorized: bool = False


class STSRuntime:
    """The STS services, sharing one conversion lock so the GPU runs one job at a time."""

    def __init__(
        self,
        settings: STSSettings | None = None,
        *,
        voices: Any | None = None,
        engine: Any | None = None,
    ) -> None:
        self.settings = settings or STSSettings.from_env()
        data_dir = self.settings.data_dir
        self.voices = voices or WorkspaceVoices(max_reference_bytes=self.settings.max_reference_bytes)
        self.engine = engine or OpenVoiceEngine(device=self.settings.engine_device)
        lock = threading.Lock()
        self.conversions = ConversionService(data_dir, self.voices, self.engine, conversion_lock=lock)
        self.youtube = YouTubeJobService(data_dir, self.voices, self.engine, conversion_lock=lock)
        self.media = MediaStore(data_dir)
        self.audio_jobs = AudioJobs(data_dir, self.conversions)
        self.storage_cleanup = StorageCleanup(
            data_dir,
            completed_job_retention=timedelta(days=self.settings.video_job_retention_days),
            failed_job_retention=timedelta(hours=self.settings.failed_video_job_retention_hours),
            orphan_video_input_retention=timedelta(hours=self.settings.orphan_video_input_retention_hours),
        )
        self.startup_cleanup: dict[str, Any] | None = None

    def startup(self) -> None:
        # Cleanup is manifest-driven and confined to the STS job/input folders.
        self.audio_jobs.recover_interrupted()
        self.startup_cleanup = self.storage_cleanup.run_startup_cleanup()


_runtime: STSRuntime | None = None
_runtime_lock = threading.Lock()


def get_runtime() -> STSRuntime:
    global _runtime
    with _runtime_lock:
        if _runtime is None:
            _runtime = STSRuntime()
        return _runtime


def set_runtime(runtime: STSRuntime | None) -> None:
    """Replace the process-wide STS runtime (tests, or a data-dir change)."""
    global _runtime
    with _runtime_lock:
        _runtime = runtime


def run_sts_startup() -> None:
    """Recover interrupted jobs and prune expired STS media. Never blocks app startup on failure."""
    try:
        get_runtime().startup()
    except Exception:
        logger.exception("STS startup maintenance failed")


def _call(operation: Any) -> Any:
    try:
        return operation()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except VoiceWorkspaceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OpenVoiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _media_response(path: Path) -> FileResponse:
    media_type, _ = mimetypes.guess_type(path.name)
    return FileResponse(
        path,
        media_type=media_type or "application/octet-stream",
        headers={
            "Cache-Control": "no-store",
            "Accept-Ranges": "bytes",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _resolve_media(resolve: Any) -> FileResponse:
    try:
        return _media_response(resolve())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (FileNotFoundError, YouTubeJobError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


async def _request_chunks(request: Request) -> Any:
    async for chunk in request.stream():
        if chunk:
            yield chunk


@router.get("/status")
def sts_status() -> dict[str, Any]:
    """Feature flags and readiness for the voice changer, without loading the model."""
    runtime = get_runtime()
    try:
        engine = runtime.engine.status()
    except OpenVoiceError as exc:
        engine = {"ready": False, "error": str(exc)}
    return {
        "features": STS_FEATURES,
        "engine": engine,
        "video": runtime.youtube.video_status(),
        "youtube": runtime.youtube.status(),
        "startup_cleanup": runtime.startup_cleanup,
    }


@router.get("/engine/status")
def engine_status() -> dict[str, Any]:
    return _call(get_runtime().engine.status)


@router.post("/engine/probe")
def engine_probe() -> dict[str, Any]:
    return _call(get_runtime().engine.probe)


@router.get("/voices", summary="List workspace voice profiles usable for STS")
def voices() -> list[dict[str, Any]]:
    return _call(get_runtime().voices.profiles)


@router.get("/voices/{profile_id}")
def voice(profile_id: str) -> dict[str, Any]:
    return _call(lambda: get_runtime().voices.profile(profile_id))


@router.get("/voices/{profile_id}/samples")
def voice_samples(profile_id: str) -> list[dict[str, Any]]:
    return _call(lambda: get_runtime().voices.samples(profile_id))


def _select_sample(profile_id: str, sample_id: str | None) -> str:
    available = _call(lambda: get_runtime().voices.samples(profile_id))
    if not available:
        raise HTTPException(422, "This voice has no reference samples; choose a cloned voice.")
    if sample_id is None:
        if len(available) != 1:
            raise HTTPException(422, "This voice has multiple samples; provide sample_id.")
        return str(available[0]["id"])
    if not any(item.get("id") == sample_id for item in available):
        raise HTTPException(422, "sample_id does not belong to this voice.")
    return sample_id


@router.post("/inputs")
async def upload_input(request: Request, filename: str = Query(min_length=1, max_length=255)) -> dict[str, Any]:
    """Store raw audio bytes (the request body, not a multipart form) for conversion."""
    try:
        return await get_runtime().media.store_input(
            filename, _request_chunks(request), request.headers.get("content-type")
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not store input: {exc}") from exc


@router.post("/video-inputs")
async def upload_video_input(
    request: Request, filename: str = Query(min_length=1, max_length=255)
) -> dict[str, Any]:
    """Store raw video bytes (the request body, not a multipart form) for conversion."""
    try:
        return await get_runtime().media.store_video_input(
            filename, _request_chunks(request), request.headers.get("content-type")
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not store video: {exc}") from exc


@router.post("/conversions")
def convert(request: ConversionRequest) -> dict[str, Any]:
    """Convert a stored input synchronously and return the completed manifest."""
    runtime = get_runtime()
    try:
        return runtime.conversions.convert(
            runtime.media.resolve_input(request.input_id),
            request.profile_id,
            request.sample_id,
            tau=request.tau,
            pitch_semitones=request.pitch_semitones,
            brightness_db=request.brightness_db,
        )
    except (ValueError, FileNotFoundError, VoiceWorkspaceError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (OpenVoiceError, AudioEffectsError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _enqueue_audio(values: dict[str, Any], tasks: BackgroundTasks, response: Response) -> dict[str, Any]:
    runtime = get_runtime()
    job = runtime.audio_jobs.create(values)
    tasks.add_task(runtime.audio_jobs.run, job["job_id"], runtime.media)
    response.headers["Location"] = job["status_url"]
    response.headers["Retry-After"] = "2"
    return job


@router.post("/audio/jobs", status_code=202)
def create_audio_job(options: AudioJobRequest, background_tasks: BackgroundTasks, response: Response) -> dict[str, Any]:
    """Convert an existing upload in the background. Poll status_url for completion."""
    if not options.authorized:
        raise HTTPException(422, "Set authorized=true to confirm permission to use the media and voice.")
    try:
        get_runtime().media.resolve_input(str(options.input_id))
    except FileNotFoundError as exc:
        raise HTTPException(404, "Uploaded audio not found.") from exc
    values = options.model_dump(mode="json")
    values["sample_id"] = _select_sample(values["profile_id"], values["sample_id"])
    return _enqueue_audio(values, background_tasks, response)


@router.post(
    "/speech",
    status_code=202,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
async def speech(
    request: Request,
    background_tasks: BackgroundTasks,
    response: Response,
    profile_id: UUID,
    filename: str = Query(min_length=1, max_length=255),
    sample_id: UUID | None = None,
    authorized: bool = False,
    tau: float = Query(default=0.3, ge=0, le=1),
    pitch_semitones: float = Query(default=0, ge=-MAX_PITCH_SEMITONES, le=MAX_PITCH_SEMITONES),
    brightness_db: float = Query(default=0, ge=-MAX_BRIGHTNESS_DB, le=MAX_BRIGHTNESS_DB),
) -> dict[str, Any]:
    """Upload raw audio bytes and queue conversion; this is not a multipart form."""
    if not authorized:
        raise HTTPException(422, "Set authorized=true to confirm permission to use the media and voice.")
    # Database and filesystem lookups are blocking, so run them off the event loop.
    selected = await run_in_threadpool(_select_sample, str(profile_id), str(sample_id) if sample_id else None)
    upload = await upload_input(request, filename)
    values = AudioJobRequest(
        input_id=upload["input_id"],
        profile_id=profile_id,
        sample_id=selected,
        authorized=True,
        tau=tau,
        pitch_semitones=pitch_semitones,
        brightness_db=brightness_db,
    )
    return _enqueue_audio(values.model_dump(mode="json"), background_tasks, response)


@router.get("/audio/jobs")
def list_audio_jobs(
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)
) -> dict[str, Any]:
    return {"items": get_runtime().audio_jobs.list(limit, offset), "limit": limit, "offset": offset}


@router.get("/audio/jobs/{job_id}")
def audio_job(job_id: UUID) -> dict[str, Any]:
    try:
        return get_runtime().audio_jobs.get(str(job_id))
    except FileNotFoundError as exc:
        raise HTTPException(404, "Audio job not found.") from exc


@router.get("/audio/jobs/{job_id}/audio", response_class=FileResponse)
def download_audio(job_id: UUID) -> FileResponse:
    job = audio_job(job_id)
    if job["status"] != "completed":
        raise HTTPException(409, f"Audio is unavailable: job is {job['status']}.")
    try:
        path = get_runtime().media.resolve_output(job["conversion_id"])
    except FileNotFoundError as exc:
        raise HTTPException(404, "Output audio no longer exists.") from exc
    return FileResponse(
        path,
        media_type="audio/wav",
        filename=f"{job_id}.wav",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/media/inputs/{input_id}", response_class=FileResponse)
def input_media(input_id: str) -> FileResponse:
    return _resolve_media(lambda: get_runtime().media.resolve_input(input_id))


@router.get("/media/video-inputs/{video_input_id}", response_class=FileResponse)
def video_input_media(video_input_id: str) -> FileResponse:
    return _resolve_media(lambda: get_runtime().media.resolve_video_input(video_input_id))


@router.get("/media/outputs/{job_id}", response_class=FileResponse)
def output_media(job_id: str) -> FileResponse:
    return _resolve_media(lambda: get_runtime().media.resolve_output(job_id))


@router.get("/media/video-jobs/{job_id}", response_class=FileResponse)
def video_output_media(job_id: str) -> FileResponse:
    return _resolve_media(lambda: get_runtime().youtube.resolve_output(job_id))


def _delete(operation: Any) -> dict[str, bool]:
    try:
        operation()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MediaInUseError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"deleted": True}


@router.delete("/inputs/{input_id}")
def delete_input(input_id: str) -> dict[str, bool]:
    """Delete an uploaded audio file, unless a queued or running job still needs it."""
    runtime = get_runtime()

    def delete() -> None:
        runtime.media.resolve_input(input_id)  # validates the ID and 404s before the in-use check
        if runtime.audio_jobs.input_in_use(input_id):
            raise MediaInUseError("This audio is being converted; wait for the job to finish.")
        runtime.media.delete_input(input_id)

    return _delete(delete)


@router.delete("/video-inputs/{video_input_id}")
def delete_video_input(video_input_id: str) -> dict[str, bool]:
    """Delete an imported video, unless a queued or running job still needs it."""
    runtime = get_runtime()

    def delete() -> None:
        runtime.media.resolve_video_input(video_input_id)
        if runtime.youtube.video_input_in_use(video_input_id):
            raise MediaInUseError("This video is being converted; wait for the job to finish.")
        runtime.media.delete_video_input(video_input_id)

    return _delete(delete)


@router.delete("/audio/jobs/{job_id}")
def delete_audio_job(job_id: UUID) -> dict[str, bool]:
    """Delete a finished audio job and its converted WAV."""
    runtime = get_runtime()
    return _delete(lambda: runtime.audio_jobs.delete(str(job_id), runtime.media))


@router.delete("/video/jobs/{job_id}")
@router.delete("/youtube/jobs/{job_id}")
def delete_video_job(job_id: str) -> dict[str, bool]:
    """Delete a finished video job and its output video; a cached YouTube source is kept."""
    return _delete(lambda: get_runtime().youtube.delete_job(job_id))


@router.get("/media/youtube-cache/source", response_class=FileResponse)
def youtube_cache_source_media() -> FileResponse:
    return _resolve_media(get_runtime().youtube.resolve_cached_source)


@router.get("/youtube/status")
def youtube_status() -> dict[str, Any]:
    return get_runtime().youtube.status()


@router.get("/video/status")
def video_status() -> dict[str, Any]:
    return get_runtime().youtube.video_status()


@router.get("/youtube/cache")
def youtube_cache_status() -> dict[str, Any]:
    return get_runtime().youtube.cache_status()


@router.delete("/youtube/cache")
def clear_youtube_cache() -> dict[str, Any]:
    try:
        return get_runtime().youtube.clear_cache()
    except YouTubeJobError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _job_or_error(operation: Any) -> dict[str, Any]:
    try:
        return operation()
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except YouTubeJobError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/youtube/jobs", status_code=202)
def create_youtube_job(request: YouTubeJobRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    youtube = get_runtime().youtube
    job = _job_or_error(
        lambda: youtube.create_job(
            request.youtube_url,
            request.profile_id,
            request.sample_id,
            tau=request.tau,
            pitch_semitones=request.pitch_semitones,
            brightness_db=request.brightness_db,
            output_format=request.output_format,
            authorized=request.authorized,
        )
    )
    background_tasks.add_task(youtube.run_job, job["job_id"])
    return job


@router.get("/youtube/jobs/{job_id}")
def youtube_job(job_id: str) -> dict[str, Any]:
    return _job_or_error(lambda: get_runtime().youtube.get_job(job_id))


@router.post("/video/jobs", status_code=202)
def create_local_video_job(request: LocalVideoJobRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    runtime = get_runtime()

    def create() -> dict[str, Any]:
        try:
            upload = runtime.media.describe_video_input(request.video_input_id)
            source = runtime.media.resolve_video_input(request.video_input_id)
        except FileNotFoundError as exc:
            # A missing upload is a bad request here, not a missing job.
            raise ValueError(str(exc)) from exc
        return runtime.youtube.create_local_job(
            source,
            request.video_input_id,
            str(upload["original_name"]),
            request.profile_id,
            request.sample_id,
            tau=request.tau,
            pitch_semitones=request.pitch_semitones,
            brightness_db=request.brightness_db,
            output_format=request.output_format,
            authorized=request.authorized,
        )

    job = _job_or_error(create)
    background_tasks.add_task(runtime.youtube.run_job, job["job_id"])
    return job


@router.get("/video/jobs/{job_id}")
def video_job(job_id: str) -> dict[str, Any]:
    return _job_or_error(lambda: get_runtime().youtube.get_job(job_id))
