import { useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { type NewRule, ROOT, type RuleTier, type RuleView, type RulesFile, addRules, countActive, mergeRules, useRuleState } from "../../lib/rules";
import AddRuleDialog from "./AddRuleDialog";
import { RuleList } from "./RuleTree";

const SECTIONS: { tier: RuleTier; title: string }[] = [
  { tier: "hard", title: "Hard rules" },
  { tier: "custom", title: "Customized rules" },
];

/** The global rule card: hard and customized rules with a tick each, and "Add rule" at the bottom. */
export default function RuleCard({ file }: { file: RulesFile }) {
  const state = useRuleState();
  const rules = useMemo(() => mergeRules(file.rules, state), [file.rules, state]);
  const entityLabel = useMemo(() => {
    const labels = new Map(file.entities.map((e) => [e.id, e.label]));
    return (id: string) => labels.get(id) ?? id;
  }, [file.entities]);
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());
  // undefined = closed, null = new top-level rule, RuleView = new sub-rule of that rule
  const [dialog, setDialog] = useState<RuleView | null | undefined>(undefined);

  const toggleCollapse = (id: string) =>
    setCollapsed((c) => {
      const next = new Set(c);
      if (!next.delete(id)) next.add(id);
      return next;
    });

  const apply = (parent: RuleView | null, added: NewRule[]) => {
    addRules(parent?.id ?? ROOT, added);
    if (parent) setCollapsed((c) => new Set([...c].filter((id) => id !== parent.id)));
  };

  const tree = { collapsed, onToggleCollapse: toggleCollapse, onAddSub: (r: RuleView) => setDialog(r), entityLabel };

  return (
    <section aria-labelledby="rules-card-title" className="max-w-2xl rounded-xl border border-neutral-200 bg-white p-5 shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
      <header className="flex items-baseline justify-between gap-3">
        <h2 id="rules-card-title" className="text-[15px] font-semibold text-neutral-900">
          Rules
        </h2>
        <span className="text-xs text-neutral-500 tabular-nums">{countActive(rules)} active</span>
      </header>

      {SECTIONS.map(({ tier, title }) => {
        const list = rules.filter((r) => r.tier === tier);
        return (
          <div key={tier} className="mt-5">
            <h3 id={`rules-${tier}`} className="mb-1 pl-1 text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
              {title}
            </h3>
            <div role="group" aria-labelledby={`rules-${tier}`}>
              {list.length ? <RuleList rules={list} {...tree} /> : <p className="pl-1 text-sm text-neutral-400">None</p>}
            </div>
          </div>
        );
      })}

      <button
        id="add-rule-button"
        type="button"
        onClick={() => setDialog(null)}
        className="mt-5 flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-neutral-300 px-3 py-2.5 text-sm font-medium text-neutral-600 transition-colors duration-150 hover:border-accent-500 hover:bg-accent-50/50 hover:text-accent-700"
      >
        <Plus className="size-4" aria-hidden />
        Add rule
      </button>

      {dialog !== undefined && (
        <AddRuleDialog
          entities={file.entities}
          parent={dialog}
          onApply={(added) => apply(dialog, added)}
          onClose={() => setDialog(undefined)}
        />
      )}
    </section>
  );
}
