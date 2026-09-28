import { Search, X } from "lucide-react";
import { useId, useMemo, useState } from "react";
import type { TechMeta } from "../lib/api";

type Props = {
  all: TechMeta[];
  selected: string[];
  colorOf: (tech: string) => string;
  onAdd: (tech: string) => void;
  onRemove: (tech: string) => void;
  max?: number;
};

/** Search-and-chip picker; chip keys show the series colour that follows each technology. */
export function TechPicker({ all, selected, colorOf, onAdd, onRemove, max = 8 }: Props) {
  const [query, setQuery] = useState("");
  const listId = useId();
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return all.filter((t) => t.tech.toLowerCase().includes(q) && !selected.includes(t.tech)).slice(0, 8);
  }, [all, query, selected]);
  const full = selected.length >= max;

  return (
    <div className="picker">
      <div className="chips">
        {selected.map((tech) => (
          <button key={tech} type="button" className="chip" onClick={() => onRemove(tech)} aria-label={`Remove ${tech}`}>
            <span className="chip__key" style={{ background: colorOf(tech) }} />
            {tech}
            <X className="chip__x" aria-hidden />
          </button>
        ))}
      </div>
      <div className="picker__search">
        <Search size={15} aria-hidden className="picker__icon" />
        <input
          className="input" placeholder={full ? `Remove one to add more (max ${max})` : "Add a technology"} disabled={full}
          value={query} onChange={(e) => setQuery(e.target.value)} aria-controls={listId} aria-label="Add a technology"
          onKeyDown={(e) => {
            if (e.key === "Enter" && matches[0]) {
              onAdd(matches[0].tech);
              setQuery("");
            }
            if (e.key === "Escape") setQuery("");
          }}
        />
        {matches.length > 0 && (
          <ul id={listId} className="picker__list" role="listbox">
            {matches.map((m) => (
              <li key={m.tech} role="option" aria-selected={false}>
                <button type="button" onClick={() => { onAdd(m.tech); setQuery(""); }}>
                  {m.tech} <span className="muted small">{m.first_year}–{m.last_year}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

/** Stable colour slots: a technology keeps its colour while selected; freed slots are reused. */
export function useColorSlots(initial: string[]) {
  const [slots, setSlots] = useState<Record<string, number>>(() => Object.fromEntries(initial.map((t, i) => [t, i])));
  const selected = Object.keys(slots).sort((a, b) => slots[a] - slots[b]);
  const add = (tech: string) =>
    setSlots((s) => {
      if (tech in s) return s;
      const used = new Set(Object.values(s));
      const free = [0, 1, 2, 3, 4, 5, 6, 7].find((i) => !used.has(i));
      return free === undefined ? s : { ...s, [tech]: free };
    });
  const remove = (tech: string) =>
    setSlots((s) => {
      const next = { ...s };
      delete next[tech];
      return next;
    });
  return { selected, slots, add, remove };
}
