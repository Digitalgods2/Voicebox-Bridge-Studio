import { Link, Outlet, useMatchRoute } from '@tanstack/react-router';
import { useTranslation } from 'react-i18next';
import { BOTTOM_SAFE_AREA_PADDING } from '@/lib/constants/ui';
import { cn } from '@/lib/utils/cn';
import { usePlatform } from '@/platform/PlatformContext';
import { usePlayerStore } from '@/stores/playerStore';

interface SettingsTab {
  labelKey?: string;
  label?: string;
  path:
    | '/settings'
    | '/settings/generation'
    | '/settings/captures'
    | '/settings/mcp'
    | '/settings/gpu'
    | '/settings/logs'
    | '/settings/changelog'
    | '/settings/about';
  tauriOnly?: boolean;
  tip: string;
}

const tabs: SettingsTab[] = [
  {
    labelKey: 'settings.tabs.general',
    path: '/settings',
    tip: 'Server connection, language, and general app behaviour',
  },
  {
    labelKey: 'settings.tabs.generation',
    path: '/settings/generation',
    tip: 'Defaults for text-to-speech generation',
  },
  {
    labelKey: 'settings.tabs.captures',
    path: '/settings/captures',
    tip: 'Recording, dictation, transcription, and capture storage',
  },
  {
    labelKey: 'settings.tabs.mcp',
    path: '/settings/mcp',
    tip: 'Let local AI assistants speak through your voices over MCP',
  },
  {
    labelKey: 'settings.tabs.gpu',
    path: '/settings/gpu',
    tauriOnly: true,
    tip: 'GPU acceleration for faster generation',
  },
  {
    labelKey: 'settings.tabs.logs',
    path: '/settings/logs',
    tauriOnly: true,
    tip: 'Backend server logs for troubleshooting',
  },
  {
    labelKey: 'settings.tabs.changelog',
    path: '/settings/changelog',
    tip: 'What changed in each VoiceBox release',
  },
  {
    labelKey: 'settings.tabs.about',
    path: '/settings/about',
    tip: 'About VoiceBox Bridge Studio, credits, and license',
  },
];

export function SettingsLayout() {
  const { t } = useTranslation();
  const platform = usePlatform();
  const isPlayerVisible = !!usePlayerStore((state) => state.audioUrl);
  const matchRoute = useMatchRoute();

  return (
    <div className="flex flex-col h-full min-h-0">
      <h1 className="brand-title text-3xl shrink-0 pt-1 pb-3">{t('nav.settings')}</h1>
      <nav className="flex gap-1 border-b border-accent/20 shrink-0">
        {tabs.map((tab) => {
          if (tab.tauriOnly && !platform.metadata.isTauri) return null;

          const isActive =
            tab.path === '/settings'
              ? matchRoute({ to: tab.path, fuzzy: false })
              : matchRoute({ to: tab.path });

          return (
            <Link
              key={tab.path}
              to={tab.path}
              data-tip={tab.tip}
              className={cn(
                'px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px',
                isActive
                  ? 'border-accent text-accent'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:border-accent/30',
              )}
            >
              {tab.label ?? (tab.labelKey ? t(tab.labelKey) : '')}
            </Link>
          );
        })}
      </nav>

      <div
        className={cn(
          'flex-1 overflow-y-auto pt-6 pb-6 px-2 -mx-2',
          isPlayerVisible && BOTTOM_SAFE_AREA_PADDING,
        )}
      >
        <Outlet />
      </div>
    </div>
  );
}
