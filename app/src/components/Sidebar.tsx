import { Link, useMatchRoute } from '@tanstack/react-router';
import {
  AudioLines,
  AudioWaveform,
  Box,
  Captions,
  type LucideIcon,
  Mic,
  Settings,
  Volume2,
  Wand2,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import appLogo from '@/assets/app-logo.png';
import { cn } from '@/lib/utils/cn';
import { usePlatform } from '@/platform/PlatformContext';
import type { UpdateStatus } from '@/platform/types';
import { usePlayerStore } from '@/stores/playerStore';
import { version } from '../../package.json';

interface SidebarProps {
  isMacOS?: boolean;
}

const tabs: Array<{
  id: string;
  path: string;
  icon: LucideIcon;
  labelKey?: string;
  label?: string;
  tip: string;
}> = [
  {
    id: 'main',
    path: '/',
    icon: Volume2,
    labelKey: 'nav.generate',
    tip: 'Generate: type text and speak it in one of your voices',
  },
  {
    id: 'stories',
    path: '/stories',
    icon: AudioLines,
    labelKey: 'nav.stories',
    tip: 'Stories: arrange clips from several voices into a multi-track timeline',
  },
  {
    id: 'captures',
    path: '/captures',
    icon: Captions,
    labelKey: 'nav.captures',
    tip: 'Captures: recordings and dictations, transcribed locally',
  },
  {
    id: 'voices',
    path: '/voices',
    icon: Mic,
    labelKey: 'nav.voices',
    tip: 'Voices: your voice profiles, their samples, and per-voice effects',
  },
  {
    id: 'speech-to-speech',
    path: '/speech-to-speech',
    icon: AudioWaveform,
    labelKey: 'nav.speechToSpeech',
    tip: 'Speech to Speech: re-voice audio, video files, or YouTube videos while keeping the original timing and delivery',
  },
  {
    id: 'effects',
    path: '/effects',
    icon: Wand2,
    labelKey: 'nav.effects',
    tip: 'Effects: build reusable effect chains such as pitch, reverb, and EQ',
  },
  {
    id: 'models',
    path: '/models',
    icon: Box,
    labelKey: 'nav.models',
    tip: 'Models: download, load, and remove local speech models',
  },
  {
    id: 'settings',
    path: '/settings',
    icon: Settings,
    labelKey: 'nav.settings',
    tip: 'Settings: server, GPU, generation, captures, logs, and about',
  },
];

export function Sidebar({ isMacOS }: SidebarProps) {
  const { t } = useTranslation();
  const matchRoute = useMatchRoute();
  const isPlayerOpen = !!usePlayerStore((s) => s.audioUrl);
  const platform = usePlatform();

  const [updateStatus, setUpdateStatus] = useState<UpdateStatus>(platform.updater.getStatus());
  useEffect(() => platform.updater.subscribe(setUpdateStatus), [platform.updater]);

  return (
    <div
      data-tip-side="right"
      className={cn(
        'fixed left-0 top-0 h-full w-[var(--sidebar-width)] bg-sidebar border-r border-accent/20 flex flex-col items-center py-5 gap-4',
        isMacOS && 'pt-12',
      )}
    >
      {/* Logo */}
      <Link
        to="/settings/about"
        className="flex flex-col items-center gap-1.5 px-2 shrink-0"
        data-tip="About VoiceBox Bridge Studio, credits, and license"
      >
        <img
          src={appLogo}
          alt="VoiceBox Bridge Studio"
          className="sidebar-logo w-28 h-28 object-contain"
        />
        <span className="text-center text-[11px] font-semibold leading-tight tracking-wide text-accent">
          VoiceBox Bridge
          <br />
          Studio
        </span>
      </Link>

      {/* Navigation: icon tiles with their names, gold for the current screen */}
      <nav className="flex w-full flex-1 min-h-0 flex-col items-center gap-1.5 overflow-y-auto px-3">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const label = tab.label ?? (tab.labelKey ? t(tab.labelKey) : tab.id);
          const isActive =
            tab.path === '/'
              ? matchRoute({ to: '/', fuzzy: false })
              : matchRoute({ to: tab.path, fuzzy: true });

          return (
            <Link
              key={tab.id}
              to={tab.path}
              className={cn(
                'group flex w-full shrink-0 flex-col items-center justify-center gap-1 rounded-xl border py-2 transition-all duration-200',
                isActive
                  ? 'border-accent/45 bg-accent/12 text-accent shadow-[0_0_18px_-6px_rgba(214,167,79,0.55)]'
                  : 'border-transparent text-muted-foreground hover:border-accent/20 hover:bg-accent/8 hover:text-foreground',
              )}
              data-tip={tab.tip}
              aria-current={isActive ? 'page' : undefined}
            >
              <Icon className="h-5 w-5" />
              <span className="text-[11px] font-medium leading-none">{label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Version */}
      <div
        className="mt-auto flex flex-col items-center gap-1.5 transition-all duration-300"
        style={{ paddingBottom: isPlayerOpen ? '7rem' : undefined }}
      >
        <span className="text-[10px] text-muted-foreground/80" data-tip="Installed app version">
          v{version}
        </span>
        {updateStatus.available && (
          <Link
            to="/settings"
            className="text-[9px] font-semibold tracking-wide uppercase px-2 py-0.5 rounded-full bg-accent/15 text-accent hover:bg-accent/25 transition-colors"
          >
            {t('nav.updateBadge')}
          </Link>
        )}
      </div>
    </div>
  );
}
