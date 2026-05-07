import { type ReactNode, useState } from "react";

interface RadioOption<V> { value: V; label: string }

export function TweaksPanel({ title = "Tweaks", children }: { title?: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  if (!open) {
    return (
      <button className="twk-fab" aria-label="Open tweaks" onClick={() => setOpen(true)}>
        ⚙
      </button>
    );
  }
  return (
    <div className="twk-panel" data-noncommentable="">
      <div className="twk-hd">
        <b>{title}</b>
        <button className="twk-x" aria-label="Close tweaks" onClick={() => setOpen(false)}>✕</button>
      </div>
      <div className="twk-body">{children}</div>
    </div>
  );
}

export function TweakSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <>
      <div className="twk-sect">{title}</div>
      {children}
    </>
  );
}

export function TweakRadio<V extends string>({
  label, value, options, onChange,
}: {
  label: string;
  value: V;
  options: RadioOption<V>[];
  onChange: (v: V) => void;
}) {
  const idx = Math.max(0, options.findIndex((o) => o.value === value));
  return (
    <div className="twk-row">
      <div className="twk-lbl"><span>{label}</span></div>
      <div className="twk-seg" role="radiogroup">
        <div
          className="twk-seg-thumb"
          style={{
            left: `calc(2px + ${idx} * (100% - 4px) / ${options.length})`,
            width: `calc((100% - 4px) / ${options.length})`,
          }}
        />
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={o.value === value}
            onClick={() => onChange(o.value)}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}
