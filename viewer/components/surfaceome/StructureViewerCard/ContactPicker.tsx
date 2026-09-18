"use client";
import { useRef } from "react";
import styles from "./StructureViewerCard.module.css";

/** Native disclosure keyboard behavior; ordinary buttons keep every option accessible. */
export function ContactPicker({ label, value, placeholder, groups, onChange }: {
  label: string; value: string; placeholder: string;
  groups: {label?: string; options: string[]}[]; onChange: (value: string) => void;
}) {
  const disclosure = useRef<HTMLDetailsElement>(null);
  const choose = (next: string) => {
    onChange(next);
    disclosure.current?.removeAttribute("open");
    disclosure.current?.querySelector("summary")?.focus();
  };
  return <div className={styles.contactPicker}>
    <details ref={disclosure} onKeyDown={event => {
      if (event.key === "Escape") { disclosure.current?.removeAttribute("open"); disclosure.current?.querySelector("summary")?.focus(); }
    }}>
      <summary aria-label={`${label}: ${value || placeholder}`}>
        <span className={styles.contactPickerValue}><span className={styles.contactPickerPrefix}>{label}</span>{value || placeholder}</span>
        <svg aria-hidden="true" width="12" height="12" viewBox="0 0 16 16" fill="none"><path d="m4 6 4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </summary>
      <div className={styles.contactPickerMenu}>
        <button type="button" aria-pressed={!value} onClick={() => choose("")}>{placeholder}</button>
        {groups.filter(group => group.options.length).map((group,index) => <div key={index}>
          {group.label && <span className={styles.contactPickerLabel}>{group.label}</span>}
          {group.options.map(option => <button key={option} type="button" aria-pressed={value === option} onClick={() => choose(option)}>{option}</button>)}
        </div>)}
      </div>
    </details>
  </div>;
}
