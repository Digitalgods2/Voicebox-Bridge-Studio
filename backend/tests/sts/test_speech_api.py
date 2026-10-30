from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import time
from uuid import uuid4
import wave

from fastapi import FastAPI
import pytest
from fastapi.testclient import TestClient

from backend.routes import sts as api
from backend.sts.audio_jobs import AudioJobs
from backend.sts.settings import STSSettings


class FakeVoices:
    def __init__(self, profile, sample):
        self.profile_id = profile
        self.sample_list = [{"id": sample}]

    def profiles(self):
        return [{"id": self.profile_id, "name": "Test voice"}]

    def samples(self, profile_id):
        return self.sample_list if profile_id == self.profile_id else []

    def fetch_reference(self, *args, **kwargs):
        return {"wav_path": "reference.wav"}


@pytest.fixture
def endpoint(tmp_path, monkeypatch):
    profile, sample = str(uuid4()), str(uuid4())
    pcm = BytesIO()
    with wave.open(pcm, "wb") as wav:
        wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        wav.writeframes(b"\x00\x01" * 1600)
    payload = pcm.getvalue()
    voices = FakeVoices(profile, sample)

    def convert(self, source, reference, destination, **options):
        if source.read_bytes() == b"bad audio":
            raise ValueError("Audio decode failed")
        destination.write_bytes(payload)
        return {"ok": True, "audio": {"duration_seconds": 0.1}, "output_path": destination}

    monkeypatch.setattr(api.OpenVoiceEngine, "convert", convert)
    api.set_runtime(api.STSRuntime(STSSettings(data_dir=tmp_path), voices=voices))
    app = FastAPI()
    app.include_router(api.router)
    try:
        with TestClient(app) as client:
            def request(path, body=None, method=None):
                method = method or ("POST" if body is not None else "GET")
                if isinstance(body, dict):
                    response = client.request(method, path, json=body)
                else:
                    response = client.request(method, path, content=body)
                content_type = response.headers.get("Content-Type", "")
                data = response.json() if "application/json" in content_type else response.content
                return response.status_code, response.headers, data
            yield request, profile, sample, payload, voices
    finally:
        api.set_runtime(None)


def wait_job(request, url):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        status, _, job = request(url)
        assert status == 200
        if job["status"] in {"completed", "failed"}:
            return job
        time.sleep(0.02)
    pytest.fail("Job did not finish")


def test_upload_convert_poll_download_and_list(endpoint):
    request, profile, sample, payload, _ = endpoint
    assert request("/sts/voices")[2][0]["id"] == profile
    assert request(f"/sts/voices/{profile}/samples")[2] == [{"id": sample}]
    code, headers, job = request(f"/sts/speech?profile_id={profile}&filename=test.wav&authorized=true", payload)
    assert code == 202 and headers["Location"] == job["status_url"]
    assert job["status_url"].startswith("/sts/audio/jobs/")
    assert job["status"] == "queued" and job["sample_id"] == sample
    done = wait_job(request, job["status_url"])
    assert done["status"] == "completed"
    code, headers, audio = request(done["download_url"])
    assert code == 200 and "attachment" in headers["Content-Disposition"]
    with wave.open(BytesIO(audio)) as wav:
        assert wav.getnframes() == 1600
    assert request("/sts/audio/jobs?limit=1")[2]["items"][0]["job_id"] == job["job_id"]
    assert request("/sts/audio/jobs?offset=1")[2]["items"] == []


def test_reusable_upload_and_failed_job(endpoint):
    request, profile, sample, _, _ = endpoint
    upload = request("/sts/inputs?filename=bad.wav", b"bad audio")[2]
    code, _, job = request("/sts/audio/jobs", {"input_id": upload["input_id"], "profile_id": profile,
                                             "sample_id": sample, "authorized": True})
    assert code == 202
    done = wait_job(request, job["status_url"])
    assert done["status"] == "failed" and "decode" in done["error"]["message"]
    assert done["download_url"] is None
    assert request(job["status_url"] + "/audio")[0] == 409


def test_invalid_requests(endpoint):
    request, profile, _, payload, _ = endpoint
    prefix = f"/sts/speech?profile_id={profile}&filename=a.wav"
    assert request(prefix, payload)[0] == 422
    assert request(prefix + "&authorized=true&pitch_semitones=999", payload)[0] == 422
    assert request(prefix + f"&authorized=true&sample_id={uuid4()}", payload)[0] == 422
    assert request(prefix + "&authorized=true", b"")[0] == 422
    assert request(f"/sts/audio/jobs/{uuid4()}")[0] == 404
    assert request("/sts/audio/jobs/not-a-uuid")[0] == 422
    assert request("/sts/audio/jobs", {"input_id": str(uuid4()), "profile_id": profile, "authorized": True})[0] == 404
    assert "/sts/speech" in request("/openapi.json")[2]["paths"]


def test_restart_marks_abandoned_jobs_failed(tmp_path):
    jobs = AudioJobs(tmp_path, None)
    queued = jobs.create({"input_id": str(uuid4())})
    restarted = AudioJobs(tmp_path, None)
    restarted.recover_interrupted()
    assert restarted.get(queued["job_id"])["error"]["type"] == "Interrupted"


def test_reference_selection_requires_unambiguous_voice(endpoint):
    request, profile, sample, payload, voices = endpoint
    prefix = f"/sts/speech?profile_id={profile}&filename=a.wav&authorized=true"
    voices.sample_list = []
    assert "no reference" in request(prefix, payload)[2]["detail"]
    voices.sample_list = [{"id": sample}, {"id": str(uuid4())}]
    assert "multiple samples" in request(prefix, payload)[2]["detail"]
    assert request(prefix + f"&sample_id={sample}", payload)[0] == 202


def test_queued_output_is_unavailable(endpoint, monkeypatch):
    request, profile, _, payload, _ = endpoint
    monkeypatch.setattr(AudioJobs, "run", lambda *args: None)
    job = request(f"/sts/speech?profile_id={profile}&filename=a.wav&authorized=true", payload)[2]
    assert request(job["status_url"])[2]["status"] == "queued"
    assert request(job["status_url"] + "/audio")[0] == 409


def test_status_polling_during_manifest_updates(tmp_path):
    jobs = AudioJobs(tmp_path, None)
    job = jobs.create({"input_id": str(uuid4())})

    def write():
        for index in range(50):
            jobs._save(dict(job, revision=index))

    def read():
        for _ in range(100):
            assert jobs.get(job["job_id"])["job_id"] == job["job_id"]

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(write), pool.submit(read), pool.submit(read)]
        for future in futures:
            future.result()
