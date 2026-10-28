import React, {useEffect, useRef} from 'react';
import {createPortal} from 'react-dom';
import Icon, {type IconName} from './Icon';
import Explain from '../explain/MetricExplain';
import {coverageChipText, statusText, statusTone} from '../app/format';
import './primitives.css';

export function Badge({status, label}: {status: string; label?: string}) {
  return <span className={'pill ' + statusTone(status)}><span className="dot" aria-hidden="true"/>{label || statusText(status)}</span>;
}

export function Tone({tone, children}: {tone: 'ok' | 'warn' | 'danger' | 'info' | 'accent' | 'neutral'; children: React.ReactNode}) {
  return <span className={'pill ' + tone}>{children}</span>;
}

export function Callout({tone = 'info', title, children, action}: {tone?: 'info' | 'ok' | 'warn' | 'danger'; title?: React.ReactNode; children?: React.ReactNode; action?: React.ReactNode}) {
  const icon: IconName = tone === 'ok' ? 'check' : tone === 'warn' || tone === 'danger' ? 'warning' : 'info';
  return (
    <div className={'callout ' + tone} role={tone === 'danger' ? 'alert' : undefined}>
      <Icon name={icon} size={18} />
      <div className="callout-body">
        {title && <strong className="callout-title">{title}</strong>}
        {children}
      </div>
      {action && <div className="callout-action">{action}</div>}
    </div>
  );
}

export function Coverage({value, showFull, bar = false}: {value: unknown; showFull: boolean; bar?: boolean}) {
  if (value === 1 && !showFull) return null;
  return (
    <div className="coverage-summary">
      {bar && typeof value === 'number' && Number.isFinite(value) && (
        <div className="coverage" aria-hidden="true"><i style={{width: Math.round(Math.min(1, Math.max(0, value)) * 100) + '%'}}/></div>
      )}
      <small className="coverage-line">{coverageChipText(value)} <Explain term="coverage" compact /></small>
    </div>
  );
}

export function EmptyState({icon = 'target', title, children, actions}: {icon?: IconName; title: React.ReactNode; children?: React.ReactNode; actions?: React.ReactNode}) {
  return (
    <section className="empty">
      <div className="reticle"><Icon name={icon} size={28} /></div>
      <h2>{title}</h2>
      {children && <div className="empty-copy">{children}</div>}
      {actions && <div className="empty-actions">{actions}</div>}
    </section>
  );
}

export type SegmentedOption = {value: string; label: string; icon?: IconName; hint?: string; disabled?: boolean};

export function Segmented({value, options, onChange, label, className}: {value: string; options: SegmentedOption[]; onChange: (value: string) => void; label: string; className?: string}) {
  return (
    <div className={'segmented' + (className ? ' ' + className : '')} role="group" aria-label={label}>
      {options.map(option => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          title={option.hint}
          disabled={option.disabled}
          onClick={() => onChange(option.value)}
          onKeyDown={event => {
            if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
            event.preventDefault();
            const buttons = Array.from((event.currentTarget.parentElement?.querySelectorAll('button') || [])) as HTMLButtonElement[];
            const index = buttons.indexOf(event.currentTarget);
            const next = buttons[(index + (event.key === 'ArrowRight' ? 1 : buttons.length - 1)) % buttons.length];
            next?.focus();
            next?.click();
          }}
        >
          {option.icon && <Icon name={option.icon} size={15} />}
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function Field({label, hint, children, className}: {label: React.ReactNode; hint?: React.ReactNode; children: React.ReactNode; className?: string}) {
  return (
    <label className={'field' + (className ? ' ' + className : '')}>
      <span className="field-label">{label}</span>
      {children}
      {hint && <small className="field-hint">{hint}</small>}
    </label>
  );
}

export function Modal({open, onClose, title, eyebrow, children, footer, side = false, size = 'md', label}: {
  open: boolean;
  onClose: () => void;
  title: React.ReactNode;
  eyebrow?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  side?: boolean;
  size?: 'sm' | 'md' | 'lg';
  label?: string;
}) {
  const panel = useRef<HTMLDivElement | null>(null);
  const lastFocus = useRef<Element | null>(null);

  useEffect(() => {
    if (!open) return;
    lastFocus.current = document.activeElement;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const timer = window.setTimeout(() => { panel.current?.focus(); }, 30);
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
      if (event.key !== 'Tab' || !panel.current) return;
      const nodes = Array.from(panel.current.querySelectorAll<HTMLElement>('button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])')).filter(node => node.offsetParent !== null);
      if (!nodes.length) return;
      const first = nodes[0], last = nodes[nodes.length - 1];
      if (document.activeElement === panel.current) { event.preventDefault(); (event.shiftKey ? last : first).focus(); }
      else if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      window.clearTimeout(timer);
      document.body.style.overflow = previous;
      document.removeEventListener('keydown', onKey);
      if (lastFocus.current instanceof HTMLElement) lastFocus.current.focus();
    };
  }, [open, onClose]);

  if (!open) return null;
  return createPortal(
    <div className="overlay modal-overlay" onPointerDown={event => { if (event.target === event.currentTarget) onClose(); }}>
      <div ref={panel} className={'modal ' + size + (side ? ' side' : '')} tabIndex={-1} role="dialog" aria-modal="true" aria-label={label || (typeof title === 'string' ? title : '对话框')}>
        <header className="modal-head">
          <div>
            {eyebrow && <span className="eyebrow">{eyebrow}</span>}
            <h2>{title}</h2>
          </div>
          <button type="button" className="icon-button ghost" onClick={onClose} aria-label="关闭"><Icon name="x" size={17} /></button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="modal-foot">{footer}</footer>}
      </div>
    </div>,
    document.body,
  );
}

export function Spinner({label}: {label?: string}) {
  return <span className="spinner-wrap" role="status"><span className="spinner" aria-hidden="true"/>{label && <span>{label}</span>}</span>;
}

export function KeyHint({children}: {children: React.ReactNode}) {
  return <kbd className="key-hint">{children}</kbd>;
}
