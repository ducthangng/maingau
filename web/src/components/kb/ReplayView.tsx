import { ArrowRight } from "lucide-react";
import { OFFER_NAME } from "../worklist/model";
import { channelLabel } from "../nba/ui";
import { mockName } from "../../lib/customerMock";
import { useLoad } from "../../lib/data";

// Knowledge Base "Event replay" (deep dive B): the events after the 30.09 snapshot replayed in arrival order, and the
// pending cards they revoked or changed. Data: scripts/replay_demo.py --export web/public/data/replay.json.

interface Transition {
  event_type: string;
  ingested_at: string;
  delay_hours: number;
  pending_status: string | null;
  revoked_by: string[];
}

interface Replay {
  events: number;
  verdicts: Record<string, number>;
  customers: Record<string, { verdict: string; t0_chosen: string; after_chosen: string; transitions: Transition[] }>;
}

let cache: Promise<Replay> | null = null;
const load = () =>
  (cache ??= fetch(`${import.meta.env.BASE_URL}data/replay.json`).then((r) => {
    if (!r.ok) throw new Error(`replay.json: HTTP ${r.status}`);
    return r.json() as Promise<Replay>;
  }));

const action = (t: string) => {
  if (!t || t === "NO_ACTION") return "No action";
  const [offer, channel] = t.split("|");
  return `${OFFER_NAME[offer] ?? offer} · ${channelLabel(channel)}`;
};

export default function ReplayView() {
  const data = useLoad(load, []);
  if (data.status === "loading") return <p className="py-12 text-center text-neutral-500">Loading the event replay…</p>;
  if (data.status === "error") return <p className="text-red-700">Could not load the event replay: {data.error}</p>;
  const d = data.data;
  const rows = Object.entries(d.customers)
    .map(([cid, c]) => ({ cid, c, ev: c.transitions.find((t) => t.pending_status === "revoked") ?? c.transitions[c.transitions.length - 1] }))
    .sort((a, b) => (a.ev?.ingested_at ?? "").localeCompare(b.ev?.ingested_at ?? ""));

  return (
    <div className="max-w-4xl space-y-4">
      <p className="text-sm text-neutral-600">
        {d.events} events after the snapshot, replayed in the order they arrived. A pending card is checked again after every event: {" "}
        <span className="font-medium text-neutral-900">{d.verdicts.REVOKED ?? 0} revoked</span>, {d.verdicts.SUPERSEDED ?? 0} changed,{" "}
        {d.verdicts.UNCHANGED ?? 0} still valid. Nothing had been sent: cards wait for approval.
      </p>
      <ul className="divide-y divide-neutral-100 rounded-2xl border border-neutral-200 bg-white">
        {rows.map(({ cid, c, ev }) => (
          <li key={cid} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-sm">
            <span className="w-44 shrink-0">
              <span className="font-medium text-neutral-900">{mockName(cid)}</span>{" "}
              <span className="font-mono text-[12px] text-neutral-500">{cid}</span>
            </span>
            <span className="w-56 shrink-0 text-neutral-700">
              {ev?.event_type.replace(/_/g, " ")}{" "}
              <span className="text-[12px] tabular-nums text-neutral-500">{ev?.ingested_at.slice(11, 16)}</span>
              {ev && ev.delay_hours >= 1 && (
                <span className="ml-1.5 rounded bg-neutral-100 px-1.5 py-0.5 text-[11px] text-neutral-700">{ev.delay_hours.toFixed(1)} h late</span>
              )}
            </span>
            <span className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
              <span className="text-neutral-500 line-through decoration-neutral-300">{action(c.t0_chosen)}</span>
              <ArrowRight size={13} className="text-neutral-400" aria-hidden />
              <span className="text-neutral-900">{action(c.after_chosen)}</span>
            </span>
            <span
              className={`rounded-md px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset ${
                c.verdict === "REVOKED" ? "bg-red-50 text-red-700 ring-red-200" : "bg-neutral-100 text-neutral-700 ring-neutral-200"
              }`}
              title={ev?.revoked_by.length ? `Revoked by ${ev.revoked_by.join(", ")}` : undefined}
            >
              {c.verdict === "REVOKED" ? `Revoked · ${ev?.revoked_by[0] ?? "rule"}` : "Changed"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
