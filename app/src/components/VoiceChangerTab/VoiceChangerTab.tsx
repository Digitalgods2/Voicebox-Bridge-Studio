import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  Download,
  FileAudio,
  FileVideo,
  Loader2,
  Trash2,
  X,
  Youtube,
} from 'lucide-react';
import { type ReactNode, useEffect, useMemo, useState } from 'react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/components/ui/use-toast';
import { apiClient } from '@/lib/api/client';
import {
  type STSAdjustments,
  type STSAudioJob,
  type STSOutputFormat,
  type STSUpload,
  type STSVideoJob,
  stsApi,
  stsUrl,
} from '@/lib/api/sts';
import { cn } from '@/lib/utils/cn';

const DEFAULT_ADJUSTMENTS: STSAdjustments = { tau: 0.3, pitch_semitones: 0, brightness_db: 0 };
const ADJUSTMENTS_KEY = 'voice-changer-profile-adjustments-v1';

const STAGE_LABELS: Record<string, string> = {
  queued: 'Queued',
  downloading: 'Downloading video',
  using_cached_download: 'Using cached download',
  extracting_audio: 'Extracting audio',
  preparing_chunks: 'Preparing chunks',
  converting_chunks: 'Converting voice',
  reconstructing_audio: 'Reconstructing timeline',
  post_processing_audio: 'Applying pitch and tone',
  remuxing_video: 'Remuxing video',
  validating_output: 'Validating output',
  completed: 'Completed',
  failed: 'Failed',
};

function loadAdjustments(profileId: string, defaultPitch: number): STSAdjustments {
  // A voice starts at the pitch of its own pitch-shift effect until you save adjustments for it.
  const defaults = { ...DEFAULT_ADJUSTMENTS, pitch_semitones: defaultPitch };
  try {
    const saved = JSON.parse(localStorage.getItem(ADJUSTMENTS_KEY) ?? '{}');
    return { ...defaults, ...(saved[profileId] ?? {}) };
  } catch {
    return defaults;
  }
}

function saveAdjustments(profileId: string, adjustments: STSAdjustments) {
  try {
    const saved = JSON.parse(localStorage.getItem(ADJUSTMENTS_KEY) ?? '{}');
    saved[profileId] = adjustments;
    localStorage.setItem(ADJUSTMENTS_KEY, JSON.stringify(saved));
  } catch {
    // Remembering adjustments is a convenience; conversion works without it.
  }
}

function isActive(status?: string) {
  return status === 'queued' || status === 'running';
}

export function VoiceChangerTab() {
  const [profileId, setProfileId] = useState('');
  const [sampleId, setSampleId] = useState('');
  const [adjustments, setAdjustments] = useState<STSAdjustments>(DEFAULT_ADJUSTMENTS);
  const [authorized, setAuthorized] = useState(false);

  const status = useQuery({
    queryKey: ['sts', 'status'],
    queryFn: stsApi.status,
    refetchInterval: 30_000,
  });
  const voices = useQuery({ queryKey: ['sts', 'voices'], queryFn: stsApi.voices });
  const samples = useQuery({
    queryKey: ['sts', 'samples', profileId],
    queryFn: () => stsApi.samples(profileId),
    enabled: !!profileId,
  });

  // A sole reference sample is selected automatically.
  useEffect(() => {
    const list = samples.data ?? [];
    setSampleId(list.length === 1 ? list[0].id : '');
  }, [samples.data]);

  const defaultPitch =
    voices.data?.find((voice) => voice.id === profileId)?.default_pitch_semitones ?? 0;
  useEffect(() => {
    if (profileId) setAdjustments(loadAdjustments(profileId, defaultPitch));
  }, [profileId, defaultPitch]);

  const updateAdjustment = (key: keyof STSAdjustments, value: number) => {
    const next = { ...adjustments, [key]: value };
    setAdjustments(next);
    if (profileId) saveAdjustments(profileId, next);
  };

  const engineReady = status.data?.engine.ready ?? false;
  const selection = profileId && sampleId ? { profile_id: profileId, sample_id: sampleId } : null;
  const blocker = !engineReady
    ? 'The speech-to-speech engine is not installed or not ready.'
    : !selection
      ? 'Choose a voice and reference sample.'
      : !authorized
        ? 'Confirm you have permission to use this media and voice.'
        : null;
  const request = selection ? { ...selection, ...adjustments, authorized } : null;

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="shrink-0 pb-4">
        <h1 className="brand-title text-3xl leading-tight">Speech to Speech</h1>
        <p className="text-sm text-muted-foreground">
          Convert speech into one of your voices while keeping the original timing, pacing, and
          delivery.
        </p>
      </div>

      {status.data && !engineReady && <EngineNotice status={status.data.engine} />}

      <div className="flex-1 min-h-0 overflow-y-auto pb-8">
        <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
          <section className="space-y-5 rounded-xl border border-accent/20 bg-card/70 p-5 h-fit shadow-[0_12px_40px_-20px_rgba(0,0,0,0.9)]">
            <div className="space-y-2">
              <Label>Target voice</Label>
              <Select value={profileId} onValueChange={setProfileId}>
                <SelectTrigger>
                  <SelectValue
                    placeholder={voices.isLoading ? 'Loading voices…' : 'Choose a voice'}
                  />
                </SelectTrigger>
                <SelectContent>
                  {(voices.data ?? []).map((voice) => (
                    <SelectItem key={voice.id} value={voice.id} disabled={voice.sample_count === 0}>
                      {voice.name}
                      {voice.sample_count === 0 ? ' (no reference samples)' : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {voices.error && <p className="text-xs text-destructive">{String(voices.error)}</p>}
            </div>

            {profileId && (samples.data?.length ?? 0) > 1 && (
              <div className="space-y-2">
                <Label>Reference sample</Label>
                <Select value={sampleId} onValueChange={setSampleId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Choose a sample" />
                  </SelectTrigger>
                  <SelectContent>
                    {(samples.data ?? []).map((sample, index) => (
                      <SelectItem key={sample.id} value={sample.id}>
                        {sample.reference_text?.slice(0, 48) || `Sample ${index + 1}`}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {sampleId && (
              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground">Reference</Label>
                <MediaPreview kind="audio" src={apiClient.getSampleUrl(sampleId)} className="h-9" />
              </div>
            )}

            <AdjustmentSlider
              label="Voice similarity (tau)"
              value={adjustments.tau}
              min={0}
              max={1}
              step={0.05}
              format={(v) => v.toFixed(2)}
              onChange={(v) => updateAdjustment('tau', v)}
            />
            <AdjustmentSlider
              label="Pitch correction"
              value={adjustments.pitch_semitones}
              min={-6}
              max={6}
              step={0.5}
              format={(v) => `${v > 0 ? '+' : ''}${v} st`}
              onChange={(v) => updateAdjustment('pitch_semitones', v)}
            />
            <AdjustmentSlider
              label="Tone (deeper ↔ brighter)"
              value={adjustments.brightness_db}
              min={-6}
              max={6}
              step={0.5}
              format={(v) => `${v > 0 ? '+' : ''}${v} dB`}
              onChange={(v) => updateAdjustment('brightness_db', v)}
            />
            {profileId && (
              <p className="text-xs text-muted-foreground">
                Adjustments are remembered for each voice.
              </p>
            )}

            <label
              htmlFor="sts-authorized"
              className="flex items-start gap-2 text-sm cursor-pointer"
            >
              <Checkbox
                id="sts-authorized"
                checked={authorized}
                onCheckedChange={setAuthorized}
                className="mt-0.5"
              />
              <span>I own or have permission to use this media and this voice.</span>
            </label>
          </section>

          <section className="rounded-xl border border-accent/20 bg-card/70 p-5 min-w-0 shadow-[0_12px_40px_-20px_rgba(0,0,0,0.9)]">
            <Tabs defaultValue="audio">
              <TabsList>
                <TabsTrigger value="audio" className="gap-1.5">
                  <FileAudio className="h-4 w-4" /> Audio file
                </TabsTrigger>
                <TabsTrigger value="video" className="gap-1.5">
                  <FileVideo className="h-4 w-4" /> Video file
                </TabsTrigger>
                <TabsTrigger value="youtube" className="gap-1.5">
                  <Youtube className="h-4 w-4" /> YouTube
                </TabsTrigger>
              </TabsList>
              <TabsContent value="audio" className="pt-4">
                <AudioWorkflow request={request} blocker={blocker} />
              </TabsContent>
              <TabsContent value="video" className="pt-4">
                <VideoWorkflow request={request} blocker={blocker} />
              </TabsContent>
              <TabsContent value="youtube" className="pt-4">
                <YouTubeWorkflow request={request} blocker={blocker} />
              </TabsContent>
            </Tabs>
          </section>
        </div>
      </div>
    </div>
  );
}

type ConversionRequest =
  | (STSAdjustments & { profile_id: string; sample_id: string; authorized: boolean })
  | null;

interface WorkflowProps {
  request: ConversionRequest;
  blocker: string | null;
}

function EngineNotice({
  status,
}: {
  status: { error?: string; checks?: Record<string, boolean> };
}) {
  const missing = Object.entries(status.checks ?? {})
    .filter(([, ok]) => !ok)
    .map(([name]) => name);
  return (
    <div className="mb-4 flex gap-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 text-sm">
      <AlertTriangle className="h-5 w-5 shrink-0 text-amber-500" />
      <div className="space-y-1">
        <p className="font-medium">The speech-to-speech engine is not ready.</p>
        <p className="text-muted-foreground">
          {status.error ??
            (missing.length > 0
              ? `Missing: ${missing.join(', ')}.`
              : 'Check the installation steps.')}{' '}
          Install the isolated OpenVoice V2 runtime described in docs/sts/engine-install.md.
        </p>
      </div>
    </div>
  );
}

function AdjustmentSlider(props: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format: (value: number) => string;
  onChange: (value: number) => void;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label>{props.label}</Label>
        <span className="text-xs font-mono text-muted-foreground">{props.format(props.value)}</span>
      </div>
      <Slider
        value={[props.value]}
        min={props.min}
        max={props.max}
        step={props.step}
        onValueChange={([value]) => props.onChange(value)}
      />
    </div>
  );
}

function FilePicker(props: {
  accept: string;
  label: string;
  onFile: (file: File) => void;
  disabled?: boolean;
}) {
  return (
    <Input
      type="file"
      accept={props.accept}
      aria-label={props.label}
      disabled={props.disabled}
      onChange={(event) => {
        const file = event.target.files?.[0];
        if (file) props.onFile(file);
      }}
    />
  );
}

function OutputFormatSelect(props: {
  value: STSOutputFormat;
  onChange: (value: STSOutputFormat) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <Label className="shrink-0">Output</Label>
      <Select value={props.value} onValueChange={(v) => props.onChange(v as STSOutputFormat)}>
        <SelectTrigger className="w-56">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="mkv">MKV (lossless FLAC audio)</SelectItem>
          <SelectItem value="mp4">MP4 (AAC audio, widest support)</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}

function ConvertBar(props: {
  blocker: string | null;
  busy: boolean;
  ready: boolean;
  onConvert: () => void;
}) {
  const hint = props.blocker ?? (props.ready ? null : 'Choose a source first.');
  return (
    <div className="flex items-center gap-3">
      <Button onClick={props.onConvert} disabled={!!hint || props.busy}>
        {props.busy && <Loader2 className="h-4 w-4 animate-spin" />}
        Convert
      </Button>
      {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
    </div>
  );
}

function MediaPreview({
  kind,
  src,
  className,
}: {
  kind: 'audio' | 'video';
  src: string;
  className?: string;
}) {
  // These previews play the user's own source and converted files, which carry no caption tracks.
  if (kind === 'audio') {
    // biome-ignore lint/a11y/useMediaCaption: user-supplied media has no caption track to offer
    return <audio controls src={src} className={cn('w-full', className)} />;
  }
  return (
    // biome-ignore lint/a11y/useMediaCaption: user-supplied media has no caption track to offer
    <video controls src={src} className={cn('w-full max-h-96 rounded-md bg-black', className)} />
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="space-y-2">
      <Label className="brand-label text-xs">{title}</Label>
      {children}
    </div>
  );
}

function useFailureToast(title = 'Conversion failed') {
  const { toast } = useToast();
  return (error: unknown) =>
    toast({
      title,
      description: error instanceof Error ? error.message : String(error),
      variant: 'destructive',
    });
}

/** Clears a source: removes the upload from the app's storage and resets the picker. */
function ClearButton(props: { onClear: () => void; disabled?: boolean; pending?: boolean }) {
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={props.onClear}
      disabled={props.disabled || props.pending}
      className="shrink-0"
    >
      {props.pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <X className="h-4 w-4" />}
      Clear
    </Button>
  );
}

/** Deletes a result after confirmation; it can't be undone. */
function DeleteResultButton(props: { what: string; onConfirm: () => void; pending?: boolean }) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          disabled={props.pending}
          className="text-destructive hover:text-destructive hover:border-destructive/60 hover:bg-destructive/10"
        >
          {props.pending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Trash2 className="h-4 w-4" />
          )}
          Delete
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete this {props.what}?</AlertDialogTitle>
          <AlertDialogDescription>
            The converted file and its job record are removed from this computer. This can't be
            undone. Your source and voices are not affected.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={props.onConfirm}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

/**
 * Stops and unloads every player showing a file whose URL contains `id`.
 * Windows can't delete a file the app is still streaming to a player.
 * Returns a function that reloads those players if the deletion fails.
 */
function releasePlayers(id: string): () => void {
  const released: Array<[HTMLMediaElement, string]> = [];
  for (const player of document.querySelectorAll<HTMLMediaElement>('audio, video')) {
    const src = player.getAttribute('src') ?? '';
    if (!src.includes(id)) continue;
    player.pause();
    player.removeAttribute('src');
    player.load();
    released.push([player, src]);
  }
  return () => {
    for (const [player, src] of released) player.setAttribute('src', src);
  };
}

/** Removes a file the page may be playing, restoring the players if removal fails. */
async function removeReleasingPlayers(id: string, remove: (id: string) => Promise<unknown>) {
  const restore = releasePlayers(id);
  try {
    await remove(id);
  } catch (error) {
    restore();
    throw error;
  }
}

/** Upload state for one source kind, with clearing and replacement cleanup. */
function useSourceUpload(
  upload: (file: File) => Promise<STSUpload>,
  remove: (id: string) => Promise<unknown>,
  idOf: (upload: STSUpload) => string | undefined,
) {
  const notifyFailure = useFailureToast('Could not use that file');
  const notifyClearFailure = useFailureToast('Could not clear the source');
  const [current, setCurrent] = useState<STSUpload | null>(null);
  // Changing the key remounts the file input, which empties its selection.
  const [pickerKey, setPickerKey] = useState(0);

  const uploadMutation = useMutation({
    mutationFn: upload,
    onSuccess: (next) => {
      const previous = current && idOf(current);
      setCurrent(next);
      // A replaced upload is no longer reachable from the page; remove it quietly.
      if (previous) remove(previous).catch(() => undefined);
    },
    onError: notifyFailure,
  });
  const clearMutation = useMutation({
    mutationFn: async () => {
      const id = current && idOf(current);
      if (id) await removeReleasingPlayers(id, remove);
    },
    onSuccess: () => {
      setCurrent(null);
      setPickerKey((key) => key + 1);
    },
    onError: notifyClearFailure,
  });

  return { current, pickerKey, uploadMutation, clearMutation };
}

/** Deletes a finished job's output and forgets it on the page. */
function useDeleteResult(
  remove: (jobId: string) => Promise<unknown>,
  jobId: string | null,
  onDeleted: () => void,
) {
  const queryClient = useQueryClient();
  const notifyFailure = useFailureToast('Could not delete the result');
  return useMutation({
    mutationFn: async () => {
      // Result URLs contain the job ID: /sts/audio/jobs/{id}/audio and /sts/media/video-jobs/{id}.
      if (jobId) await removeReleasingPlayers(jobId, remove);
    },
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ['sts', 'audio-job', jobId] });
      queryClient.removeQueries({ queryKey: ['sts', 'video-job', jobId] });
      onDeleted();
    },
    onError: notifyFailure,
  });
}

function AudioWorkflow({ request, blocker }: WorkflowProps) {
  const notifyFailure = useFailureToast();
  const [jobId, setJobId] = useState<string | null>(null);
  const source = useSourceUpload(stsApi.uploadAudio, stsApi.deleteAudioInput, (u) => u.input_id);
  const upload = source.current;

  const convertMutation = useMutation({
    mutationFn: () => {
      if (!request || !upload?.input_id) throw new Error('Choose a voice and an audio file first.');
      return stsApi.createAudioJob({ ...request, input_id: upload.input_id });
    },
    onSuccess: (job) => setJobId(job.job_id),
    onError: notifyFailure,
  });
  const job = useQuery({
    queryKey: ['sts', 'audio-job', jobId],
    queryFn: () => stsApi.audioJob(jobId as string),
    enabled: !!jobId,
    refetchInterval: (query) => (isActive(query.state.data?.status) ? 1000 : false),
  });
  const deleteResult = useDeleteResult(stsApi.deleteAudioJob, jobId, () => setJobId(null));
  const converting = convertMutation.isPending || isActive(job.data?.status);

  return (
    <div className="space-y-5">
      <Panel title="Source audio">
        <div className="flex items-center gap-2">
          <FilePicker
            key={source.pickerKey}
            accept="audio/*,.wav,.mp3,.flac,.m4a,.aac,.ogg,.opus,.wma"
            label="Source audio file"
            disabled={source.uploadMutation.isPending}
            onFile={(file) => source.uploadMutation.mutate(file)}
          />
          {upload && (
            <ClearButton
              onClear={() => source.clearMutation.mutate()}
              disabled={converting}
              pending={source.clearMutation.isPending}
            />
          )}
        </div>
        {source.uploadMutation.isPending && (
          <p className="text-xs text-muted-foreground">Uploading…</p>
        )}
        {upload && <MediaPreview kind="audio" src={stsUrl(upload.media_url)} />}
      </Panel>
      <ConvertBar
        blocker={blocker}
        ready={!!upload}
        busy={converting}
        onConvert={() => convertMutation.mutate()}
      />
      {job.data && (
        <AudioJobResult
          job={job.data}
          onDelete={() => deleteResult.mutate()}
          deleting={deleteResult.isPending}
        />
      )}
    </div>
  );
}

function AudioJobResult({
  job,
  onDelete,
  deleting,
}: {
  job: STSAudioJob;
  onDelete: () => void;
  deleting: boolean;
}) {
  if (isActive(job.status)) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Converting… this can take a while for long
        recordings.
      </p>
    );
  }
  if (job.status === 'failed') {
    return (
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-destructive">{job.error?.message ?? 'Conversion failed.'}</p>
        <DeleteResultButton what="failed conversion" onConfirm={onDelete} pending={deleting} />
      </div>
    );
  }
  if (!job.download_url) return null;
  const url = stsUrl(job.download_url);
  return (
    <Panel title="Converted audio">
      <MediaPreview kind="audio" src={url} />
      <div className="flex gap-2">
        <Button variant="outline" size="sm" asChild>
          <a href={url} download>
            <Download className="h-4 w-4" /> Download WAV
          </a>
        </Button>
        <DeleteResultButton what="converted audio" onConfirm={onDelete} pending={deleting} />
      </div>
    </Panel>
  );
}

function VideoWorkflow({ request, blocker }: WorkflowProps) {
  const notifyFailure = useFailureToast();
  const [outputFormat, setOutputFormat] = useState<STSOutputFormat>('mkv');
  const [jobId, setJobId] = useState<string | null>(null);
  const source = useSourceUpload(
    stsApi.uploadVideo,
    stsApi.deleteVideoInput,
    (u) => u.video_input_id,
  );
  const upload = source.current;

  const convertMutation = useMutation({
    mutationFn: () => {
      if (!request || !upload?.video_input_id)
        throw new Error('Choose a voice and a video file first.');
      return stsApi.createVideoJob({
        ...request,
        video_input_id: upload.video_input_id,
        output_format: outputFormat,
      });
    },
    onSuccess: (job) => setJobId(job.job_id),
    onError: notifyFailure,
  });
  const job = useVideoJob(jobId, stsApi.videoJob);
  const deleteResult = useDeleteResult(stsApi.deleteVideoJob, jobId, () => setJobId(null));
  const converting = convertMutation.isPending || isActive(job.data?.status);

  return (
    <div className="space-y-5">
      <Panel title="Source video">
        <div className="flex items-center gap-2">
          <FilePicker
            key={source.pickerKey}
            accept="video/*"
            label="Source video file"
            disabled={source.uploadMutation.isPending}
            onFile={(file) => source.uploadMutation.mutate(file)}
          />
          {upload && (
            <ClearButton
              onClear={() => source.clearMutation.mutate()}
              disabled={converting}
              pending={source.clearMutation.isPending}
            />
          )}
        </div>
        {source.uploadMutation.isPending && (
          <p className="text-xs text-muted-foreground">Uploading video…</p>
        )}
        {upload && (
          <MediaPreview kind="video" src={stsUrl(upload.media_url)} className="max-h-80" />
        )}
      </Panel>
      <OutputFormatSelect value={outputFormat} onChange={setOutputFormat} />
      <ConvertBar
        blocker={blocker}
        ready={!!upload}
        busy={converting}
        onConvert={() => convertMutation.mutate()}
      />
      {job.data && (
        <VideoJobResult
          job={job.data}
          onDelete={() => deleteResult.mutate()}
          deleting={deleteResult.isPending}
        />
      )}
    </div>
  );
}

function YouTubeWorkflow({ request, blocker }: WorkflowProps) {
  const notifyFailure = useFailureToast();
  const queryClient = useQueryClient();
  const [url, setUrl] = useState('');
  const [outputFormat, setOutputFormat] = useState<STSOutputFormat>('mkv');
  const [jobId, setJobId] = useState<string | null>(null);

  const cache = useQuery({ queryKey: ['sts', 'youtube-cache'], queryFn: stsApi.youtubeCache });
  const clearCache = useMutation({
    mutationFn: stsApi.clearYouTubeCache,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sts', 'youtube-cache'] }),
    onError: notifyFailure,
  });
  const convertMutation = useMutation({
    mutationFn: () => {
      if (!request) throw new Error('Choose a voice first.');
      return stsApi.createYouTubeJob({
        ...request,
        youtube_url: url.trim(),
        output_format: outputFormat,
      });
    },
    onSuccess: (job) => setJobId(job.job_id),
    onError: notifyFailure,
  });
  const job = useVideoJob(jobId, stsApi.youtubeJob);
  // YouTube jobs live in the same job store as local video jobs.
  const deleteResult = useDeleteResult(stsApi.deleteVideoJob, jobId, () => setJobId(null));
  const converting = convertMutation.isPending || isActive(job.data?.status);

  useEffect(() => {
    if (job.data?.status === 'completed')
      queryClient.invalidateQueries({ queryKey: ['sts', 'youtube-cache'] });
  }, [job.data?.status, queryClient]);

  return (
    <div className="space-y-5">
      <Panel title="YouTube video">
        <div className="flex items-center gap-2">
          <Input
            placeholder="https://www.youtube.com/watch?v=…"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
          />
          {url && <ClearButton onClear={() => setUrl('')} disabled={converting} />}
        </div>
        <p className="text-xs text-muted-foreground">
          One video is downloaded and kept locally so reconverting it with another voice needs no
          new download.
        </p>
      </Panel>
      {cache.data?.active && (
        <div className="flex items-center justify-between gap-3 rounded-md border p-3 text-sm">
          <div className="min-w-0">
            <p className="truncate font-medium">{cache.data.title ?? cache.data.video_id}</p>
            <p className="text-xs text-muted-foreground">
              Cached download{cache.data.channel ? ` · ${cache.data.channel}` : ''}
            </p>
          </div>
          <div className="flex shrink-0 gap-1">
            {cache.data.source_media_url && (
              <Button variant="ghost" size="sm" asChild>
                <a href={stsUrl(cache.data.source_media_url)} download>
                  <Download className="h-4 w-4" />
                </a>
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              disabled={clearCache.isPending || converting}
              onClick={() => clearCache.mutate()}
              aria-label="Clear cached download"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
      <OutputFormatSelect value={outputFormat} onChange={setOutputFormat} />
      <ConvertBar
        blocker={blocker}
        ready={url.trim().length > 0}
        busy={converting}
        onConvert={() => convertMutation.mutate()}
      />
      {job.data && (
        <VideoJobResult
          job={job.data}
          onDelete={() => deleteResult.mutate()}
          deleting={deleteResult.isPending}
        />
      )}
    </div>
  );
}

function useVideoJob(jobId: string | null, fetchJob: (jobId: string) => Promise<STSVideoJob>) {
  return useQuery({
    queryKey: ['sts', 'video-job', jobId],
    queryFn: () => fetchJob(jobId as string),
    enabled: !!jobId,
    // Keep polling through transient errors; the job manifest is durable on disk.
    retry: true,
    refetchInterval: (query) => (isActive(query.state.data?.status) ? 1500 : false),
  });
}

function VideoJobResult({
  job,
  onDelete,
  deleting,
}: {
  job: STSVideoJob;
  onDelete: () => void;
  deleting: boolean;
}) {
  const stage = useMemo(
    () => STAGE_LABELS[job.stage ?? job.status] ?? job.stage ?? job.status,
    [job],
  );
  if (job.status === 'failed') {
    return (
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-destructive">{job.error?.message ?? 'Conversion failed.'}</p>
        <DeleteResultButton what="failed conversion" onConfirm={onDelete} pending={deleting} />
      </div>
    );
  }
  if (isActive(job.status)) {
    const chunks =
      job.stage === 'converting_chunks' && job.chunk_count
        ? ` · ${job.chunks_completed ?? 0}/${job.chunk_count} chunks`
        : '';
    return (
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            {stage}
            <span className="text-muted-foreground">{chunks}</span>
          </span>
          <span className="font-mono text-xs text-muted-foreground">
            {Math.round(job.progress_percent ?? 0)}%
          </span>
        </div>
        <Progress value={job.progress_percent ?? 0} />
      </div>
    );
  }
  const url = stsUrl(job.media_url);
  return (
    <Panel title="Converted video">
      <MediaPreview kind="video" src={url} />
      <div className="flex gap-2">
        <Button variant="outline" size="sm" asChild>
          <a href={url} download>
            <Download className="h-4 w-4" /> Download {job.output_format.toUpperCase()}
          </a>
        </Button>
        <DeleteResultButton what="converted video" onConfirm={onDelete} pending={deleting} />
      </div>
    </Panel>
  );
}
