import { ArrowUpRight } from 'lucide-react';
import type { CSSProperties, ReactNode } from 'react';
import { useEffect, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import appLogo from '@/assets/app-logo.png';
import { usePlatform } from '@/platform/PlatformContext';

const CREATOR_URL = 'https://github.com/Digitalgods2';
const PROJECT_URL = 'https://github.com/Digitalgods2/Voicebox-STS-Sidecar';

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

function GitHubMark({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
    </svg>
  );
}

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
              <h1 className="text-2xl font-semibold">VoiceBox Bridge Studio</h1>
              <p className="text-xs text-muted-foreground/60 h-4">
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
              <span className="text-[11px] uppercase tracking-[0.3em] text-muted-foreground/70">
                {t('settings.about.createdBy')}
              </span>
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
              <ArrowUpRight className="h-3.5 w-3.5 text-muted-foreground/40 group-hover:text-muted-foreground transition-colors" />
            </a>
          </FadeIn>

          <FadeIn delay={400}>
            <div className="w-full rounded-lg border border-border/60 px-5 py-3 space-y-2">
              <p className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground/70">
                {t('settings.about.foundationHeading')}
              </p>
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
            <p className="text-xs text-muted-foreground/50 pt-2">
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
