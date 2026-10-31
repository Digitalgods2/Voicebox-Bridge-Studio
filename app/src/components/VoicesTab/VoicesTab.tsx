import { Mic, Plus, Search, Sparkles } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ProfileForm } from '@/components/VoiceProfiles/ProfileForm';
import type { VoiceProfileResponse } from '@/lib/api/types';
import { BOTTOM_SAFE_AREA_PADDING } from '@/lib/constants/ui';
import { useProfiles } from '@/lib/hooks/useProfiles';
import { cn } from '@/lib/utils/cn';
import { usePlayerStore } from '@/stores/playerStore';
import { useServerStore } from '@/stores/serverStore';
import { useUIStore } from '@/stores/uiStore';
import { VoiceInspector } from './VoiceInspector';

export function VoicesTab() {
  const { t } = useTranslation();
  const { data: profiles, isLoading } = useProfiles();
  const setDialogOpen = useUIStore((state) => state.setProfileDialogOpen);
  const selectedVoiceId = useUIStore((state) => state.selectedVoiceId);
  const setSelectedVoiceId = useUIStore((state) => state.setSelectedVoiceId);
  const scrollRef = useRef<HTMLDivElement>(null);
  const audioUrl = usePlayerStore((state) => state.audioUrl);
  const isPlayerVisible = !!audioUrl;
  const [search, setSearch] = useState('');

  const filteredProfiles = useMemo(() => {
    if (!profiles) return [];
    if (!search.trim()) return profiles;
    const q = search.toLowerCase();
    return profiles.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.description?.toLowerCase().includes(q) ||
        p.language.toLowerCase().includes(q),
    );
  }, [profiles, search]);

  // Auto-select first profile if none selected
  useEffect(() => {
    if (!selectedVoiceId && profiles && profiles.length > 0) {
      setSelectedVoiceId(profiles[0].id);
    }
    // Clear selection if selected profile was deleted
    if (selectedVoiceId && profiles && !profiles.find((p) => p.id === selectedVoiceId)) {
      setSelectedVoiceId(profiles.length > 0 ? profiles[0].id : null);
    }
  }, [profiles, selectedVoiceId, setSelectedVoiceId]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-muted-foreground">{t('voicesTab.loading')}</div>
      </div>
    );
  }

  return (
    <div className="h-full flex gap-0 overflow-hidden -mx-8">
      {/* Left: Table */}
      <div className="flex-1 min-w-0 flex flex-col relative overflow-hidden">
        {/* Scroll Mask */}
        <div className="absolute top-0 left-0 right-0 h-16 bg-gradient-to-b from-background to-transparent z-10 pointer-events-none" />

        {/* Fixed Header */}
        <div className="absolute top-0 left-0 right-0 z-20 pl-8 pr-8">
          <div className="flex items-center gap-3 mb-6">
            <h1 className="brand-title text-3xl leading-tight">{t('voicesTab.title')}</h1>
            <div className="flex-1" />
            <div className="relative w-[240px]">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder={t('voicesTab.searchPlaceholder')}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-10 pl-8 text-sm rounded-full focus-visible:ring-0 focus-visible:ring-offset-0"
                data-tip="Filter voices by name, description, or language"
              />
            </div>
            <Button
              onClick={() => setDialogOpen(true)}
              data-tip="Create a voice profile by cloning a recording or uploading samples"
            >
              <Plus className="h-4 w-4 mr-2" />
              {t('voicesTab.newVoice')}
            </Button>
          </div>
        </div>

        {/* Scrollable Content */}
        <div
          ref={scrollRef}
          className={cn(
            'flex-1 overflow-y-auto overflow-x-hidden pt-16 relative z-0',
            isPlayerVisible && BOTTOM_SAFE_AREA_PADDING,
          )}
        >
          <Table className="table-fixed [&_td:first-child]:pl-8 [&_th:first-child]:pl-8">
            <TableHeader>
              <TableRow>
                <TableHead className="w-[40%]" data-tip="Profile name and description">
                  {t('voicesTab.columns.name')}
                </TableHead>
                <TableHead className="w-[13%]" data-tip="Language the voice speaks when generating">
                  {t('voicesTab.columns.language')}
                </TableHead>
                <TableHead className="w-[15%]" data-tip="Speech clips generated with this voice">
                  {t('voicesTab.columns.generations')}
                </TableHead>
                <TableHead
                  className="w-[13%]"
                  data-tip="Reference recordings the voice is cloned from. Speech to Speech needs at least one."
                >
                  {t('voicesTab.columns.samples')}
                </TableHead>
                <TableHead
                  className="w-[13%]"
                  data-tip="Audio effects applied automatically to this voice's output"
                >
                  {t('voicesTab.columns.effects')}
                </TableHead>
                <TableHead className="w-6"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredProfiles.map((profile) => (
                <VoiceRow
                  key={profile.id}
                  profile={profile}
                  isSelected={selectedVoiceId === profile.id}
                  onSelect={() => setSelectedVoiceId(profile.id)}
                />
              ))}
            </TableBody>
          </Table>
        </div>
      </div>

      {/* Right: Inspector */}
      {selectedVoiceId && (
        <div className="w-[340px] shrink-0 border-l border-t rounded-tl-xl bg-muted/30">
          <VoiceInspector key={selectedVoiceId} profileId={selectedVoiceId} />
        </div>
      )}

      <ProfileForm />
    </div>
  );
}

interface VoiceRowProps {
  profile: VoiceProfileResponse;
  isSelected: boolean;
  onSelect: () => void;
}

function VoiceRow({ profile, isSelected, onSelect }: VoiceRowProps) {
  const { t } = useTranslation();
  const serverUrl = useServerStore((state) => state.serverUrl);
  const [avatarError, setAvatarError] = useState(false);
  const avatarUrl = profile.avatar_path ? `${serverUrl}/profiles/${profile.id}/avatar` : null;

  const enabledEffects = profile.effects_chain?.filter((e) => e.enabled) ?? [];
  const effectsSummary = enabledEffects.map((e) => e.type).join(' → ');

  return (
    <TableRow
      className={cn('cursor-pointer', isSelected ? 'bg-muted/50' : 'hover:bg-muted/50')}
      onClick={onSelect}
    >
      <TableCell>
        <div className="flex w-full min-w-0 items-center gap-2">
          <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center shrink-0 overflow-hidden">
            {avatarUrl && !avatarError ? (
              <img
                src={avatarUrl}
                alt={t('voicesTab.avatarAlt', { name: profile.name })}
                className="h-full w-full object-cover"
                onError={() => setAvatarError(true)}
              />
            ) : (
              <Mic className="h-4 w-4 text-muted-foreground" />
            )}
          </div>
          <div className="min-w-0">
            <div className="font-medium truncate">{profile.name}</div>
            {profile.description && (
              <div className="text-sm text-muted-foreground truncate">{profile.description}</div>
            )}
          </div>
        </div>
      </TableCell>
      <TableCell>{profile.language}</TableCell>
      <TableCell>{profile.generation_count}</TableCell>
      <TableCell>{profile.sample_count}</TableCell>
      <TableCell>
        {enabledEffects.length > 0 ? (
          <span
            className="inline-flex items-center gap-1 text-xs text-accent"
            title={`Effects chain: ${effectsSummary}`}
          >
            <Sparkles className="h-3 w-3 fill-accent" />
            {enabledEffects.length}
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell />
    </TableRow>
  );
}
