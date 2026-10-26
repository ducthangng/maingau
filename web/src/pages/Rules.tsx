import { loadRules } from "../lib/rules";
import { useLoad } from "../lib/data";
import RuleCard from "../components/rules/RuleCard";

// Global rules (docs/rule-center.md): tick rules on or off and add your own, nested if needed.
// Ticks and additions stay in this browser; the engine does not read them yet.
export default function Rules() {
  const file = useLoad(loadRules, []);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">Rules</h1>
      </header>
      {file.status === "loading" && <p className="text-neutral-500">Loading…</p>}
      {file.status === "error" && <p className="text-red-700">Could not load rules.json: {file.error}</p>}
      {file.status === "ready" && <RuleCard file={file.data} />}
    </div>
  );
}
