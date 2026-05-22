import { ReactNode } from 'react';

export function Panel({ title, action, children, className = '' }: { title?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={`panel ${className}`}>{(title || action) && <header className="between"><h2>{title}</h2>{action}</header>}{children}</section>;
}

export function Tier({ value }: { value: string }) {
  const tier = value || 'Bronze';
  return <span className={`tier tier-${tier.toLowerCase()}`}>{tier}</span>;
}

export function AvatarMark({ id }: { id?: string | null }) {
  return <span className={`avatar-mark ${id || 'academy'}`}>{(id || 'MF').slice(0, 2).toUpperCase()}</span>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}
