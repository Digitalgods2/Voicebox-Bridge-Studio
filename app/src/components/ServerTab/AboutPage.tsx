import { ArrowUpRight } from 'lucide-react';
import type { CSSProperties, ReactNode } from 'react';
import { useEffect, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import appLogo from '@/assets/app-logo.png';
import { GitHubMark } from '@/components/GitHubMark';
import { CREATOR_URL, PROJECT_URL } from '@/lib/constants/project';
import { usePlatform } from '@/platform/PlatformContext';

// The open-source projects this app is built on, credited under their MIT licenses.
const FOUNDATIONS = [
  {
    name: 'VoiceBox',
    url: 'https://github.com/jamiepine/voicebox',
    authors: 'Jamie Pine and contributors',
    roleKey: 'settings.about.voiceboxRole',
  },
  {
    name: 'OpenVoice V2',
    url: 'https://github.com/myshell-ai/OpenVoice',
    authors: 'MyShell.ai',
    roleKey: 'settings.about.openvoiceRole',
  },
];

function FadeIn({ delay = 0, children }: { delay?: number; children: ReactNode }) {
  return (
    <div
      className="animate-[fadeInUp_0.5s_ease_both]"
      style={{ animationDelay: `${delay}ms` } as CSSProperties}
    >
      {children}
    </div>
  );
}

export function AboutPage() {
  const { t } = useTranslation();
  const platform = usePlatform();
  const [version, setVersion] = useState('');

  useEffect(() => {
    platform.metadata
      .getVersion()
      .then(setVersion)
      .catch(() => setVersion(''));
  }, [platform]);

  return (
    <>
      <style>{`
        @keyframes fadeInUp {
          from {
            opacity: 0;
            transform: translateY(8px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
      {/* my-auto centers the card when it fits and lets it scroll when it does not. */}
      <div className="max-w-md mx-auto h-full overflow-y-auto flex flex-col">
        <div className="my-auto py-4 flex flex-col items-center text-center space-y-3">
          <FadeIn delay={0}>
            <img
              src={appLogo}
              alt="VoiceBox Bridge Studio"
              className="sidebar-logo w-44 h-44 object-contain"
            />
          </FadeIn>

          <FadeIn delay={80}>
            <div className="space-y-1.5">
              <h1 className="brand-title text-3xl leading-tight">VoiceBox Bridge Studio</h1>
              <p className="text-xs text-muted-foreground/80 h-4">
                {version ? `v${version}` : '\u00A0'}
              </p>
            </div>
          </FadeIn>

          <FadeIn delay={160}>
            <p className="text-sm text-muted-foreground leading-relaxed max-w-sm">
              {t('settings.about.tagline')}
            </p>
          </FadeIn>

          <FadeIn delay={240}>
            <div className="flex flex-col items-center gap-1">
              <span className="brand-label text-[11px]">{t('settings.about.createdBy')}</span>
              <a
                href={CREATOR_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xl font-semibold text-accent hover:underline"
              >
                DigitalGods
              </a>
            </div>
          </FadeIn>

          <FadeIn delay={320}>
            <a
              href={PROJECT_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="group inline-flex items-center gap-2 rounded-lg border border-border/60 px-4 py-2 text-sm transition-colors hover:bg-muted/50"
            >
              <GitHubMark className="h-4 w-4 text-muted-foreground" />
              {t('settings.about.projectSource')}
              <ArrowUpRight className="h-3.5 w-3.5 text-muted-foreground/80 group-hover:text-muted-foreground transition-colors" />
            </a>
          </FadeIn>

          <FadeIn delay={400}>
            <div className="w-full rounded-lg border border-border/60 px-5 py-3 space-y-2">
              <p className="brand-label text-[11px]">{t('settings.about.foundationHeading')}</p>
              {FOUNDATIONS.map((credit) => (
                <div key={credit.name} className="text-sm leading-relaxed">
                  <a
                    href={credit.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-foreground hover:text-accent hover:underline"
                  >
                    {credit.name}
                  </a>
                  <span className="text-muted-foreground">
                    {' '}
                    {t('settings.about.by')} {credit.authors} · MIT
                  </span>
                  <p className="text-xs text-muted-foreground/80">{t(credit.roleKey)}</p>
                </div>
              ))}
            </div>
          </FadeIn>

          <FadeIn delay={480}>
            <p className="text-xs text-muted-foreground/80 pt-2">
              <Trans
                i18nKey="settings.about.license"
                components={{
                  link: (
                    // biome-ignore lint/a11y/useAnchorContent: Trans fills content at runtime
                    <a
                      href={`${PROJECT_URL}/blob/main/NOTICE.md`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline-offset-2 hover:underline hover:text-muted-foreground transition-colors"
                    />
                  ),
                }}
              />
            </p>
          </FadeIn>
        </div>
      </div>
    </>
  );
}
