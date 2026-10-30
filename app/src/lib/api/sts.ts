import { useServerStore } from '@/stores/serverStore';

// Speech to Speech client. STS runs inside the same backend
// as TTS and reads the same voice profiles, so it shares the server URL.

export type STSOutputFormat = 'mkv' | 'mp4';

export interface STSVoice {
  id: string;
  name: string;
  description: string | null;
  language: string;
  voice_type: string;
  sample_count: number;
  /** The voice's enabled pitch-shift effect, used until adjustments are saved for it. */
  default_pitch_semitones: number;
}

export interface STSSample {
  id: string;
  profile_id: string;
  reference_text: string;
  audio_url: string;
}

export interface STSStatus {
  features: string[];
  engine: {
    ready: boolean;
    error?: string;
    checks?: Record<string, boolean>;
    configured_device?: string;
  };
  video: { ready: boolean; checks: Record<string, boolean> };
  youtube: { ready: boolean; checks?: Record<string, boolean> };
}

export interface STSAdjustments {
  tau: number;
  pitch_semitones: number;
  brightness_db: number;
}

export interface STSJobError {
  type: string;
  message: string;
}

export interface STSAudioJob {
  job_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  status_url: string;
  download_url: string | null;
  error?: STSJobError;
}

export interface STSVideoJob {
  job_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  stage?: string;
  progress_percent?: number;
  chunk_count?: number;
  chunks_completed?: number;
  media_url: string;
  output_format: STSOutputFormat;
  error?: STSJobError;
}

export interface STSDeleted {
  deleted: boolean;
}

export interface STSUpload {
  media_url: string;
  original_name: string;
  input_id?: string;
  video_input_id?: string;
}

export interface STSYouTubeCache {
  active: boolean;
  video_id?: string;
  title?: string | null;
  channel?: string | null;
  duration_seconds?: number | null;
  size_bytes?: number;
  source_media_url?: string;
}

function baseUrl(): string {
  return useServerStore.getState().serverUrl;
}

export function stsUrl(path: string): string {
  return `${baseUrl()}${path}`;
}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    const detail = body?.detail;
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((item: { msg?: string }) => item.msg ?? JSON.stringify(item)).join('; ')
          : `HTTP error! status: ${response.status}`;
    throw new Error(message);
  }
  return response.json();
}

async function getJson<T>(path: string): Promise<T> {
  return parse<T>(await fetch(stsUrl(path)));
}

async function sendJson<T>(path: string, method: string, body?: unknown): Promise<T> {
  return parse<T>(
    await fetch(stsUrl(path), {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  );
}

async function uploadRaw(path: string, file: File): Promise<STSUpload> {
  // The backend streams the raw request body to disk; this is not a multipart form.
  return parse<STSUpload>(
    await fetch(stsUrl(`${path}?filename=${encodeURIComponent(file.name)}`), {
      method: 'POST',
      headers: { 'Content-Type': file.type || 'application/octet-stream' },
      body: file,
    }),
  );
}

export const stsApi = {
  status: () => getJson<STSStatus>('/sts/status'),
  voices: () => getJson<STSVoice[]>('/sts/voices'),
  samples: (profileId: string) => getJson<STSSample[]>(`/sts/voices/${profileId}/samples`),

  uploadAudio: (file: File) => uploadRaw('/sts/inputs', file),
  uploadVideo: (file: File) => uploadRaw('/sts/video-inputs', file),
  deleteAudioInput: (inputId: string) => sendJson<STSDeleted>(`/sts/inputs/${inputId}`, 'DELETE'),
  deleteVideoInput: (videoInputId: string) =>
    sendJson<STSDeleted>(`/sts/video-inputs/${videoInputId}`, 'DELETE'),

  createAudioJob: (
    body: {
      input_id: string;
      profile_id: string;
      sample_id: string;
      authorized: boolean;
    } & STSAdjustments,
  ) => sendJson<STSAudioJob>('/sts/audio/jobs', 'POST', body),
  audioJob: (jobId: string) => getJson<STSAudioJob>(`/sts/audio/jobs/${jobId}`),
  deleteAudioJob: (jobId: string) => sendJson<STSDeleted>(`/sts/audio/jobs/${jobId}`, 'DELETE'),

  createVideoJob: (
    body: {
      video_input_id: string;
      profile_id: string;
      sample_id: string;
      output_format: STSOutputFormat;
      authorized: boolean;
    } & STSAdjustments,
  ) => sendJson<STSVideoJob>('/sts/video/jobs', 'POST', body),
  videoJob: (jobId: string) => getJson<STSVideoJob>(`/sts/video/jobs/${jobId}`),
  deleteVideoJob: (jobId: string) => sendJson<STSDeleted>(`/sts/video/jobs/${jobId}`, 'DELETE'),

  createYouTubeJob: (
    body: {
      youtube_url: string;
      profile_id: string;
      sample_id: string;
      output_format: STSOutputFormat;
      authorized: boolean;
    } & STSAdjustments,
  ) => sendJson<STSVideoJob>('/sts/youtube/jobs', 'POST', body),
  youtubeJob: (jobId: string) => getJson<STSVideoJob>(`/sts/youtube/jobs/${jobId}`),
  youtubeCache: () => getJson<STSYouTubeCache>('/sts/youtube/cache'),
  clearYouTubeCache: () => sendJson<{ cleared: boolean }>('/sts/youtube/cache', 'DELETE'),
};
