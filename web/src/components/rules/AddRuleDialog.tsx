import { type CSSProperties, useEffect, useMemo, useRef, useState } from "react";
import { CornerDownRight, Plus, X } from "lucide-react";
import type { Entity, NewRule, Operator, RuleTier, RuleView } from "../../lib/rules";

// Popup for new rules: one horizontal row per rule (Field | Operator | Set rule | Value).
// "+" on a row nests a smaller rule under it; Apply turns each root row into a rule with its sub-rules.

interface Draft {
  key: number;
  entity: string; // Entity.id, "" until chosen
  operator: string; // Operator.id, "" until chosen
  tier: RuleTier;
  value: "active" | "inactive";
  children: Draft[];
}

interface Flat {
  row: Draft;
  depth: number;
  tier: RuleTier; // effective: inherited from the root row or the parent rule
}

const TIER_LABEL: Record<RuleTier, string> = { hard: "Hard rule", custom: "Customized rule" };

// One line per row from lg up; below that Field and Operator take a line each, Set rule + Value share the third.
const COLS = "grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_auto] lg:grid-cols-[minmax(0,1fr)_minmax(0,1.35fr)_9.5rem_7rem_4.5rem]";
const CAPTION = "text-[11px] font-semibold uppercase tracking-wider text-neutral-500";
const SELECT =
  "h-9 w-full min-w-0 rounded-lg border border-neutral-200 bg-white px-2 text-sm transition-colors duration-150 hover:border-neutral-300 disabled:cursor-not-allowed disabled:bg-neutral-50 disabled:text-neutral-400 disabled:hover:border-neutral-200";
const ICON_BTN =
  "inline-flex size-8 items-center justify-center rounded-lg text-neutral-500 transition-colors duration-150 hover:bg-neutral-100 hover:text-neutral-900 disabled:pointer-events-none disabled:opacity-30";

const words = (s: string) => s.replace(/_/g, " ");

/** Indent for a nesting depth: full steps up to level 3, then a sliver, so deep rows keep their width. */
const indent = (depth: number, step: number) => `${Math.min(depth, 3) * step + Math.max(depth - 3, 0) * 0.25}rem`;

function flatten(rows: Draft[], fixedTier: RuleTier | null, depth = 0, rootTier?: RuleTier): Flat[] {
  return rows.flatMap((row) => {
    const tier = fixedTier ?? rootTier ?? row.tier;
    return [{ row, depth, tier }, ...flatten(row.children, fixedTier, depth + 1, tier)];
  });
}

function mapRows(rows: Draft[], key: number, fn: (d: Draft) => Draft | null): Draft[] {
  return rows.flatMap((d) => {
    if (d.key === key) {
      const out = fn(d);
      return out ? [out] : [];
    }
    return [{ ...d, children: mapRows(d.children, key, fn) }];
  });
}

/** Options for the Operator select, grouped by column when the entity has more than one. */
function OperatorOptions({ ops }: { ops: Operator[] }) {
  const groups = new Map<string, Operator[]>();
  for (const o of ops) groups.set(o.column, [...(groups.get(o.column) ?? []), o]);
  const options = (list: Operator[]) =>
    list.map((o) => (
      <option key={o.id} value={o.id} className="text-neutral-900">
        {o.label}
      </option>
    ));
  if (groups.size < 2) return <>{options(ops)}</>;
  return (
    <>
      {[...groups].map(([col, list]) => (
        <optgroup key={col} label={words(col)}>
          {options(list)}
        </optgroup>
      ))}
    </>
  );
}

export default function AddRuleDialog({
  entities,
  parent,
  onApply,
  onClose,
}: {
  entities: Entity[];
  parent: RuleView | null; // set: every row becomes a sub-rule of this rule
  onApply: (rules: NewRule[]) => void;
  onClose: () => void;
}) {
  const nextKey = useRef(2);
  const blank = (key: number, tier: RuleTier): Draft => ({ key, entity: "", operator: "", tier, value: "active", children: [] });
  const [rows, setRows] = useState<Draft[]>(() => [blank(1, parent?.tier ?? "custom")]);
  const [focusKey, setFocusKey] = useState<number | null>(null);
  const [shown, setShown] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const fields = useRef(new Map<number, HTMLSelectElement>());
  const closing = useRef(false);

  const entityById = useMemo(() => new Map(entities.map((e) => [e.id, e])), [entities]);
  const flat = flatten(rows, parent?.tier ?? null);
  const complete = flat.every((f) => f.row.entity && f.row.operator);
  const titleText = parent ? `Add sub-rule · ${parent.name}` : "Add rule";

  // Fade in; lock page scroll; focus the first Field and give focus back to the opener on close.
  useEffect(() => {
    const prevFocus = document.activeElement as HTMLElement | null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const raf = requestAnimationFrame(() => setShown(true));
    fields.current.get(1)?.focus();
    return () => {
      cancelAnimationFrame(raf);
      document.body.style.overflow = prevOverflow;
      prevFocus?.focus?.();
    };
  }, []);

  const requestClose = () => {
    if (closing.current) return;
    closing.current = true;
    setShown(false);
    window.setTimeout(onClose, 150);
  };

  // Esc cancels; Tab stays inside the dialog.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        requestClose();
        return;
      }
      if (e.key !== "Tab" || !panelRef.current) return;
      const focusable = panelRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), select:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && (document.activeElement === first || !panelRef.current.contains(document.activeElement))) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && (document.activeElement === last || !panelRef.current.contains(document.activeElement))) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // A new or neighbouring row takes focus after add / remove.
  useEffect(() => {
    if (focusKey === null) return;
    fields.current.get(focusKey)?.focus();
    setFocusKey(null);
  }, [focusKey]);

  const update = (key: number, patch: Partial<Draft>) => setRows((rs) => mapRows(rs, key, (d) => ({ ...d, ...patch })));

  const addChild = (key: number) => {
    const k = nextKey.current++;
    // First child, so the new row shows right under the row whose "+" was pressed.
    setRows((rs) => mapRows(rs, key, (d) => ({ ...d, children: [blank(k, d.tier), ...d.children] })));
    setFocusKey(k);
  };

  const addRoot = () => {
    const k = nextKey.current++;
    setRows((rs) => [...rs, blank(k, parent?.tier ?? "custom")]);
    setFocusKey(k);
  };

  const remove = (key: number) => {
    const i = flat.findIndex((f) => f.row.key === key);
    setRows((rs) => mapRows(rs, key, () => null));
    const next = flat[i - 1] ?? flat.slice(i + 1).find((f) => f.depth <= flat[i].depth);
    setFocusKey(next?.row.key ?? null);
  };

  const apply = () => {
    if (!complete || closing.current) return;
    const toRule = (d: Draft, tier: RuleTier): NewRule => {
      const entity = entityById.get(d.entity)!;
      const op = entity.operators.find((o) => o.id === d.operator)!;
      return {
        name: `${entity.label} · ${op.label}`,
        tier,
        active: d.value === "active",
        condition: { entity: entity.id, column: op.column, op: op.op, value: op.value, label: op.label },
        children: d.children.map((c) => toRule(c, tier)),
      };
    };
    onApply(rows.map((d) => toRule(d, parent?.tier ?? d.tier)));
    requestClose();
  };

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center p-2 sm:items-center sm:p-6" role="presentation">
      <div
        aria-hidden
        onClick={requestClose}
        className={`absolute inset-0 bg-neutral-900/25 transition-opacity duration-150 motion-reduce:transition-none ${shown ? "opacity-100" : "opacity-0"}`}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-rule-title"
        className={`relative flex max-h-[calc(100dvh-1rem)] w-full max-w-xl flex-col rounded-xl bg-white shadow-2xl ring-1 ring-neutral-200 transition duration-150 ease-out motion-reduce:transition-none sm:max-h-[calc(100dvh-3rem)] lg:max-w-5xl ${
          shown ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0"
        }`}
      >
        <h2 id="add-rule-title" className="break-words border-b border-neutral-200 px-5 py-4 text-base font-semibold tracking-tight text-neutral-900">
          {titleText}
        </h2>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          <div aria-hidden className={`mb-2 hidden gap-2 lg:grid ${CAPTION} ${COLS}`}>
            <span>Field</span>
            <span>Operator</span>
            <span>Set rule</span>
            <span>Value</span>
            <span />
          </div>

          <ul className="space-y-2">
            {flat.map((f, i) => {
              const { row, depth, tier } = f;
              const entity = entityById.get(row.entity);
              const isOnlyRoot = depth === 0 && rows.length === 1;
              const label = `row ${i + 1}`;
              const style = { "--d": indent(depth, 0.75), "--i": indent(Math.max(depth - 1, 0), 0.75) } as CSSProperties;
              // Below lg the header row is hidden: the first row names the four columns instead.
              const caption = (text: string) =>
                i === 0 && (
                  <span aria-hidden className={`mb-1 block lg:hidden ${CAPTION}`}>
                    {text}
                  </span>
                );
              return (
                <li
                  key={row.key}
                  style={style}
                  className={`grid items-center gap-2 pl-[var(--d)] lg:pl-0 ${COLS} ${
                    depth === 0 && i > 0 ? "mt-3 border-t border-neutral-100 pt-3" : ""
                  }`}
                >
                  <div className="col-span-2 min-w-0 lg:col-span-1 lg:pl-[var(--i)]">
                    {caption("Field")}
                    <div className="flex items-center gap-1">
                      {depth > 0 && <CornerDownRight className="size-4 shrink-0 text-neutral-300" aria-hidden />}
                      <select
                        ref={(el) => {
                          if (el) fields.current.set(row.key, el);
                          else fields.current.delete(row.key);
                        }}
                        aria-label={`Field, ${label}`}
                        value={row.entity}
                        onChange={(e) => update(row.key, { entity: e.target.value, operator: "" })}
                        className={`${SELECT} ${row.entity ? "text-neutral-900" : "text-neutral-400"}`}
                      >
                        <option value="" disabled>
                          Field
                        </option>
                        {entities.map((e) => (
                          <option key={e.id} value={e.id} className="text-neutral-900">
                            {e.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="col-span-2 min-w-0 lg:col-span-1">
                    {caption("Operator")}
                    <select
                      aria-label={`Operator, ${label}`}
                      value={row.operator}
                      disabled={!entity}
                      onChange={(e) => update(row.key, { operator: e.target.value })}
                      className={`${SELECT} ${row.operator ? "text-neutral-900" : "text-neutral-400"}`}
                    >
                      <option value="" disabled>
                        Operator
                      </option>
                      {entity && <OperatorOptions ops={entity.operators} />}
                    </select>
                  </div>

                  <div className="min-w-0">
                    {caption("Set rule")}
                    <select
                      aria-label={`Set rule, ${label}`}
                      value={tier}
                      disabled={depth > 0 || !!parent}
                      title={depth > 0 || parent ? "Inherited from the parent rule" : undefined}
                      onChange={(e) => update(row.key, { tier: e.target.value as RuleTier })}
                      className={`${SELECT} text-neutral-900`}
                    >
                      <option value="hard">{TIER_LABEL.hard}</option>
                      <option value="custom">{TIER_LABEL.custom}</option>
                    </select>
                  </div>

                  <div className="min-w-0">
                    {caption("Value")}
                    <select
                      aria-label={`Value, ${label}`}
                      value={row.value}
                      onChange={(e) => update(row.key, { value: e.target.value as Draft["value"] })}
                      className={`${SELECT} text-neutral-900`}
                    >
                      <option value="active">Active</option>
                      <option value="inactive">Inactive</option>
                    </select>
                  </div>

                  <div className="col-start-3 row-span-3 row-start-1 flex flex-col items-center justify-center gap-0.5 self-stretch lg:col-start-auto lg:row-span-1 lg:row-start-auto lg:flex-row lg:justify-end lg:self-auto">
                    <button type="button" onClick={() => addChild(row.key)} aria-label={`Add sub-rule under ${label}`} title="Add sub-rule" className={ICON_BTN}>
                      <Plus className="size-4" aria-hidden />
                    </button>
                    <button
                      type="button"
                      onClick={() => remove(row.key)}
                      disabled={isOnlyRoot}
                      aria-label={`Remove ${label}`}
                      title="Remove"
                      className={ICON_BTN}
                    >
                      <X className="size-4" aria-hidden />
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>

          <button
            type="button"
            onClick={addRoot}
            className="mt-3 inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-sm font-medium text-accent-700 transition-colors duration-150 hover:bg-accent-50"
          >
            <Plus className="size-4" aria-hidden />
            Row
          </button>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-neutral-200 px-5 py-3">
          <button
            type="button"
            onClick={requestClose}
            className="rounded-lg border border-neutral-200 bg-white px-3.5 py-2 text-sm font-medium text-neutral-700 transition-colors duration-150 hover:bg-neutral-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={apply}
            disabled={!complete}
            className="rounded-lg bg-accent-600 px-3.5 py-2 text-sm font-medium text-white transition-colors duration-150 hover:bg-accent-700 disabled:cursor-not-allowed disabled:bg-neutral-300"
          >
            Apply
          </button>
        </div>
      </div>
    </div>
  );
}
