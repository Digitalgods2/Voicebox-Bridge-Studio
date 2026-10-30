# Installing the speech-to-speech engine

Speech to Speech runs OpenVoice V2 in its own isolated Python 3.10
environment, separate from the app's backend environment. The backend starts
it as a subprocess, passes only file paths, and forces Hugging Face offline
mode, so the engine never downloads anything at conversion time.

Everything below lives in ignored, project-local folders:

| Path | Contents |
| --- | --- |
| `.envs/openvoice-v2/` | Isolated Python 3.10 interpreter and ML packages |
| `third_party/OpenVoice/` | OpenVoice source at a pinned revision |
| `data/models/openvoice-v2/converter/` | Converter config and checkpoint |
| `config/openvoice-v2.*` | Tracked provenance, hashes, and audited requirements |

Set `STS_ENGINE_ROOT` if these folders live somewhere other than the project
root (for example, next to a packaged build).

## Downloads

- CUDA-enabled PyTorch 2.13.0: **2,594,544,868 bytes** (about 2.42 GiB) plus
  dependencies. The CPU build is much smaller.
- OpenVoice source at a pinned Git revision.
- The OpenVoice V2 converter checkpoint: **131,320,490 bytes** (about 131 MB),
  MIT licensed.

Review these downloads and their licenses before installing them. Exact
provenance is recorded in
[`config/openvoice-v2.provenance.json`](../../config/openvoice-v2.provenance.json),
and the selection rationale in [`engine-audit.md`](engine-audit.md).

## Prerequisites

- Miniconda or another Conda-compatible installation
- Git
- FFmpeg and FFprobe on `PATH` (with the `rubberband` filter for pitch correction)
- Node.js 22 or newer (yt-dlp's YouTube JavaScript runtime)

## 1. Create the isolated environment

```powershell
conda create --prefix ".\.envs\openvoice-v2" python=3.10.20 pip -y
```

Install PyTorch first. 2.13.0 is the minimum accepted version; the worker
refuses older releases because of reviewed security advisories.

With an NVIDIA GPU:

```powershell
.\.envs\openvoice-v2\python.exe -m pip install --index-url https://download.pytorch.org/whl/cu126 torch==2.13.0
```

Without one, install the CPU build and set `STS_ENGINE_DEVICE=cpu` before
starting the app. CPU conversion works end to end but is much slower:

```powershell
.\.envs\openvoice-v2\python.exe -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.13.0
$env:STS_ENGINE_DEVICE = "cpu"
```

Install only the direct converter dependencies, not OpenVoice's full historical
requirements file (it pulls unrelated demos, transcription stacks, and
cloud-facing packages):

```powershell
.\.envs\openvoice-v2\python.exe -m pip install `
  numpy==1.26.4 `
  librosa==0.10.2.post1 `
  soundfile==0.12.1 `
  inflect==7.0.0 `
  Unidecode==1.3.7 `
  eng_to_ipa==0.0.2 `
  pypinyin==0.50.0 `
  jieba==0.42.1 `
  cn2an==0.5.22
```

The audited versions are also listed in
[`config/openvoice-v2.direct-requirements.txt`](../../config/openvoice-v2.direct-requirements.txt)
(which pins the CUDA torch build, so install torch separately as above).

## 2. Check out the pinned OpenVoice source

```powershell
git clone https://github.com/myshell-ai/OpenVoice third_party/OpenVoice
git -C third_party/OpenVoice checkout 74a1d147b17a8c3092dd5430504bd83ef6c7eb23
git -C third_party/OpenVoice rev-parse HEAD
```

The final command must print `74a1d147b17a8c3092dd5430504bd83ef6c7eb23`. The
source is imported from `third_party/OpenVoice`; it is not installed as a package.

## 3. Download and verify the converter

```powershell
$modelRevision = "f36e7edfe1684461a8343844af60babc2efbb727"
$modelBase = "https://huggingface.co/myshell-ai/OpenVoiceV2/resolve/$modelRevision/converter"
$modelDirectory = "data\models\openvoice-v2\converter"
New-Item -ItemType Directory -Path $modelDirectory -Force | Out-Null
Invoke-WebRequest -Uri "$modelBase/config.json?download=true" -OutFile "$modelDirectory\config.json"
Invoke-WebRequest -Uri "$modelBase/checkpoint.pth?download=true" -OutFile "$modelDirectory\checkpoint.pth"
(Get-FileHash "$modelDirectory\checkpoint.pth" -Algorithm SHA256).Hash.ToLower()
```

The SHA-256 must be
`9652c27e92b6b2a91632590ac9962ef7ae2b712e5c5b7f4c34ec55ee2b37ab9e`. Do not
continue if it differs; the worker also verifies it before every model load.

## 4. Verify

```powershell
backend\venv\Scripts\python -m backend.sts engine-status
backend\venv\Scripts\python -m backend.sts engine-probe
```

`engine-status` checks files and imports without loading the model.
`engine-probe` loads the model on the configured device (`cuda:0` by default;
pass `--device cpu` on a CPU-only machine) and reports device and peak memory.
In the app, the Speech to Speech screen shows a notice whenever the engine is not ready.

## Quality and timing model

What is preserved:

- The original video stream is copied with FFmpeg's `-c:v copy`; it is not re-encoded.
- Extracted, chunked, and reconstructed audio remains uncompressed 16-bit PCM.
- MKV output contains lossless FLAC audio; MP4 contains AAC for broader compatibility.
- OpenVoice runs in FP32; there is no half-precision speed shortcut.
- Long-form chunk boundaries are multiples of OpenVoice's 256-sample frame size,
  with about one second of context on either side, crossfaded over the shared context.
- The reconstructed WAV must contain exactly as many PCM frames as the extracted source.
- Pitch correction is a constant shift from -6 to +6 semitones using FFmpeg's
  high-quality Rubber Band filter, with tempo fixed at 1.0 and formants preserved.
- Tone is a -6 to +6 dB high shelf at 2.5 kHz (negative is deeper, positive brighter).
- Adjustments run once on the full converted track, followed by a safety limiter
  only when needed; any sample-rate or frame-count change is rejected.
- The output timeline must be within 50 ms of the probed video timeline, and
  FFmpeg fully decodes the result before a job is reported complete.

Limits:

- OpenVoice V2 converts at **22.05 kHz mono**. Upsampling would not restore
  information the model does not produce.
- Video jobs convert the complete soundtrack, so music, ambience, and effects
  reach the model too. Dialogue-forward sources work best. Separating and
  remixing a background bed needs a separately reviewed separation model.
