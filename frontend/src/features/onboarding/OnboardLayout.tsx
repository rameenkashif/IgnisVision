import type { ReactNode } from 'react';
import { LangSwitch } from '../../components/LangSwitch';

export function OnboardLayout({
  children,
  wide = false,
  showLang = true,
}: {
  children: ReactNode;
  wide?: boolean;
  showLang?: boolean;
}) {
  return (
    <div className="onboard-screen">
      <div className="gradient-bg" aria-hidden="true" />
      {showLang && (
        <div className="onboard-top">
          <LangSwitch />
        </div>
      )}
      <div className={`onboard-card${wide ? ' wide' : ''}`}>{children}</div>
    </div>
  );
}
