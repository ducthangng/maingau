import type { MouseEvent } from "react";
import { ChevronRight, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { type Condition, type RuleView, removeRule, setActive } from "../../lib/rules";

// One rule per row: checkbox and short name. Id, target and condition live in the tooltip only.
// Sub-rules sit under their parent on a thin guide line; unticking a parent dims them.

// Row actions show on hover and keyboard focus, and always on touch screens (no hover there).
const REVEAL =
  "opacity-0 group-hover/row:opacity-100 group-focus-within/row:opacity-100 focus-visible:opacity-100 pointer-coarse:opacity-100";
const ICON_BTN =
  "inline-flex size-7 items-center justify-center rounded-md text-neutral-400 transition duration-150 hover:bg-neutral-100 hover:text-neutral-900";

// Indent per sub-rule level, centred on the chevron: less on a phone, and only a sliver past level 3,
// so deep names keep their width.
const nest = (depth: number) => (depth < 3 ? "ml-[0.875rem] sm:pl-1.5" : "ml-1 pl-0.5");

const OP_TEXT: Record<Condition["op"], string> = { "=": "=", "!=": "≠", ">=": "≥", "<=": "≤", within_days: "within" };

export const checkboxId = (id: string) => `rule-${id}`;

/** The stored check in full: a user rule's short name may drop words. */
function conditionText(c: Condition): string {
  const words = (v: unknown) => String(v).replace(/_/g, " ");
  const value = c.op === "within_days" ? `${c.value} days` : words(c.value);
  return `${words(c.column)} ${OP_TEXT[c.op]} ${value}`;
}

function tooltip(r: RuleView, entityLabel: (id: string) => string): string {
  const lines = [r.locked ? `${r.id} · Compliance rule (legally required)` : r.id];
  if (r.target) lines.push(`Target: ${r.target}`);
  const c = r.condition;
  if (c) lines.push(`If: ${entityLabel(c.entity)} · ${r.user ? conditionText(c) : c.label}`);
  return lines.join("\n");
}

export interface TreeProps {
  collapsed: Set<string>;
  onToggleCollapse: (id: string) => void;
  onAddSub: (rule: RuleView) => void;
  entityLabel: (id: string) => string;
}

export function RuleList({
  rules,
  depth = 0,
  parentId,
  parentOn = true,
  ...props
}: TreeProps & { rules: RuleView[]; depth?: number; parentId?: string; parentOn?: boolean }) {
  return (
    <ul>
      {rules.map((r, i) => (
        <RuleRow
          key={r.id}
          rule={r}
          depth={depth}
          parentOn={parentOn}
          neighbour={rules[i - 1]?.id ?? rules[i + 1]?.id ?? parentId}
          {...props}
        />
      ))}
    </ul>
  );
}

function RuleRow({
  rule,
  depth,
  parentOn,
  neighbour,
  ...props
}: TreeProps & { rule: RuleView; depth: number; parentOn: boolean; neighbour?: string }) {
  const { collapsed, onToggleCollapse, onAddSub, entityLabel } = props;
  const hasChildren = rule.children.length > 0;
  const open = hasChildren && !collapsed.has(rule.id);
  const on = parentOn && rule.active;

  const toggle = (next: boolean) => {
    // Compliance rules are legally required: switching one off takes a second yes.
    if (!next && rule.locked && !window.confirm(`Turn off ${rule.id} "${rule.name}"? It is a legally required compliance rule.`)) return;
    setActive(rule.id, next, rule.preset);
  };

  const remove = (e: MouseEvent<HTMLButtonElement>) => {
    const fromKeyboard = e.detail === 0; // Enter or Space: no pointer involved
    removeRule(rule.id);
    // Keyboard focus moves to the nearest row; a mouse or touch removal leaves the page where it is.
    if (fromKeyboard) {
      requestAnimationFrame(() => document.getElementById(neighbour ? checkboxId(neighbour) : "add-rule-button")?.focus());
    }
  };

  return (
    <li>
      <div className="group/row flex items-center gap-1.5 rounded-lg py-1 pr-1 pl-1 transition-colors duration-150 hover:bg-neutral-50">
        {hasChildren ? (
          <button
            type="button"
            onClick={() => onToggleCollapse(rule.id)}
            aria-expanded={open}
            aria-label={`${open ? "Collapse" : "Expand"} ${rule.name}`}
            className="inline-flex size-5 shrink-0 items-center justify-center rounded text-neutral-400 transition-colors duration-150 hover:text-neutral-900"
          >
            <ChevronRight className={`size-4 transition-transform duration-150 motion-reduce:transition-none ${open ? "rotate-90" : ""}`} aria-hidden />
          </button>
        ) : (
          <span className="size-5 shrink-0" aria-hidden />
        )}
        <label title={tooltip(rule, entityLabel)} className="flex min-w-0 flex-1 cursor-pointer items-center gap-2.5 py-0.5 text-sm">
          <input
            id={checkboxId(rule.id)}
            type="checkbox"
            checked={rule.active}
            onChange={(e) => toggle(e.target.checked)}
            className="size-4 shrink-0 cursor-pointer accent-accent-600"
          />
          <span className={`min-w-0 break-words ${on ? "text-neutral-900" : "text-neutral-500"}`}>{rule.name}</span>
          {rule.locked && <ShieldCheck className="size-3.5 shrink-0 text-neutral-400" role="img" aria-label="Compliance rule" />}
        </label>
        <div className="flex shrink-0 items-center">
          <button type="button" onClick={() => onAddSub(rule)} aria-label={`Add sub-rule to ${rule.name}`} title="Add sub-rule" className={`${ICON_BTN} ${REVEAL}`}>
            <Plus className="size-4" aria-hidden />
          </button>
          {rule.user && (
            <button type="button" onClick={remove} aria-label={`Remove ${rule.name}`} title="Remove" className={`${ICON_BTN} hover:text-red-700 ${REVEAL}`}>
              <Trash2 className="size-3.5" aria-hidden />
            </button>
          )}
        </div>
      </div>
      {open && (
        <div className={`border-l border-neutral-200 transition-opacity duration-150 ${nest(depth)} ${on ? "" : "opacity-60"}`}>
          <RuleList rules={rule.children} depth={depth + 1} parentId={rule.id} parentOn={on} {...props} />
        </div>
      )}
    </li>
  );
}
