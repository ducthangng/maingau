import { useMemo, useState } from "react";
import { ChevronDown, Download, Send } from "lucide-react";
import { download, toCSV, type Decision } from "../../lib/decisions";
import { mockName } from "../../lib/customerMock";
import { executedIds, recordExecution, useExecutions, type Execution } from "../../lib/executions";
import { CHANNEL_LABEL, signedEur } from "../../lib/format";
import { ChannelIcon } from "../viz";
import { OFFER_NAME } from "./model";

// Right side of the worklist: what has been reviewed, grouped by the means of contact (channel) of
// the action that will go out (the engine's proposal or the reviewer's override). The reviewer executes one group at a time;
// executing hands the group to the campaign tool as a CSV file. Nothing is sent from here.

interface ReadyGroup {
  channel: string; // the "means": newsletter_email, outbound_call, service_agent, ...
  items: Decision[];
  sum: number | null;
}

const channelLabel = (c: string) => CHANNEL_LABEL[c] ?? c;
/** Execution keys were offer|channel before groups became per channel; read both. */
const channelOfKey = (key: string) => (key.includes("|") ? key.split("|")[1] : key);
const offerOf = (d: Decision) => d.tuple_id.split("|")[0];
const fileName = (channel: string) => `maingau-${channel}-${new Date().toISOString().slice(0, 16).replace(/[:T]/g, "")}.csv`;

function GroupCard({ g, onOpen }: { g: ReadyGroup; onOpen: (id: string) => void }) {
  const service = g.channel === "service_agent";
  const overrides = g.items.filter((d) => d.action === "overridden").length;
  // What goes out through this channel: each offer with its count, largest first.
  const offers = [...g.items.reduce((m, d) => m.set(offerOf(d), (m.get(offerOf(d)) ?? 0) + 1), new Map<string, number>())].sort(
    (a, b) => b[1] - a[1],
  );
  const execute = () => {
    download(fileName(g.channel), toCSV(g.items), "text/csv;charset=utf-8");
    recordExecution(g.channel, g.items);
  };
  return (
    <li className="space-y-3 rounded-2xl bg-white p-4 ring-1 ring-neutral-200">
      <div className="flex items-start gap-3">
        <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-neutral-900 text-white">
          <ChannelIcon channel={g.channel} size={15} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold">{channelLabel(g.channel)}</div>
          <div className="text-xs text-neutral-500">
            {g.items.length} customer{g.items.length === 1 ? "" : "s"}
            {g.sum !== null && <> · {signedEur(g.sum)} expected</>}
            {overrides > 0 && <> · {overrides} by override</>}
          </div>
        </div>
      </div>
      <p className="text-xs leading-relaxed text-neutral-600">
        {offers.map(([offer, n], i) => (
          <span key={offer}>
            {i > 0 && <span className="text-neutral-300"> · </span>}
            {OFFER_NAME[offer] ?? offer}
            {n > 1 && <span className="text-neutral-400"> ×{n}</span>}
          </span>
        ))}
      </p>
      <div className="flex flex-wrap gap-1">
        {g.items.map((d) => (
          <button
            key={d.id}
            type="button"
            onClick={() => onOpen(d.customer_id)}
            title={`${OFFER_NAME[offerOf(d)] ?? offerOf(d)} · ${d.action}${d.reason ? `: ${d.reason}` : ""}`}
            className={`rounded-md px-1.5 py-0.5 text-[11px] tabular-nums transition-colors duration-150 ${
              d.action === "overridden" ? "bg-accent-50 text-accent-700 hover:bg-accent-100" : "bg-neutral-100 text-neutral-700 hover:bg-neutral-200"
            }`}
          >
            {mockName(d.customer_id)}
          </button>
        ))}
      </div>
      <button
        type="button"
        onClick={execute}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-[background-color,transform] duration-150 hover:bg-accent-700 active:translate-y-px active:scale-[0.99]"
      >
        <Send size={15} aria-hidden />
        {service ? `Hand ${g.items.length} to service agents` : `Execute ${g.items.length} via ${channelLabel(g.channel)}`}
      </button>
    </li>
  );
}

function ExecutedList({ list }: { list: Execution[] }) {
  const [open, setOpen] = useState(false);
  if (!list.length) return null;
  return (
    <section className="space-y-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="inline-flex items-center gap-0.5 text-xs font-medium text-neutral-500 hover:text-neutral-800"
      >
        Executed ({list.length})
        <ChevronDown size={14} className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`} aria-hidden />
      </button>
      {open && (
        <ul className="space-y-1.5">
          {[...list].reverse().map((e) => {
            const ch = channelOfKey(e.tuple);
            return (
              <li key={e.id} className="flex items-center gap-2 rounded-lg bg-white px-3 py-2 text-xs ring-1 ring-neutral-200">
                <span className="min-w-0 flex-1 truncate">
                  <span className="font-medium">{channelLabel(ch)}</span> · {e.decisions.length} customer{e.decisions.length === 1 ? "" : "s"} ·{" "}
                  <span className="text-neutral-400">{e.ts.replace("T", " ").slice(0, 16)}</span>
                </span>
                <button
                  type="button"
                  onClick={() => download(fileName(ch), toCSV(e.decisions), "text/csv;charset=utf-8")}
                  className="rounded p-1 text-neutral-400 hover:bg-neutral-100 hover:text-neutral-800"
                  aria-label="Download again"
                  title="Download again"
                >
                  <Download size={13} />
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

export default function ExecutePanel({ decisions, onOpen }: { decisions: Map<string, Decision>; onOpen: (id: string) => void }) {
  const executions = useExecutions();
  const done = useMemo(() => executedIds(executions), [executions]);

  const { groups, rejected } = useMemo(() => {
    const byChannel = new Map<string, Decision[]>();
    let rejected = 0;
    for (const d of decisions.values()) {
      if (done.has(d.id)) continue;
      if (d.action === "rejected") {
        rejected++;
        continue;
      }
      // One group per means of contact (channel); the offers inside are listed on the card.
      const key = d.tuple_id.split("|")[1] ?? d.tuple_id;
      const list = byChannel.get(key);
      if (list) list.push(d);
      else byChannel.set(key, [d]);
    }
    const groups: ReadyGroup[] = [...byChannel.entries()].map(([channel, items]) => {
      const vals = items.map((d) => d.delta_clv).filter((v): v is number => typeof v === "number");
      return { channel, items, sum: vals.length ? vals.reduce((a, v) => a + v, 0) : null };
    });
    // Largest groups first, then the most expected value.
    groups.sort((a, b) => b.items.length - a.items.length || (b.sum ?? 0) - (a.sum ?? 0));
    return { groups, rejected };
  }, [decisions, done]);

  const ready = groups.reduce((a, g) => a + g.items.length, 0);

  return (
    <aside className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Ready to execute</h2>
        <p className="mt-0.5 text-sm text-neutral-500">
          {ready
            ? `${ready} reviewed, in ${groups.length} group${groups.length === 1 ? "" : "s"}. Execute one group at a time.`
            : "Approved cases appear here, grouped by channel."}
        </p>
      </div>

      {groups.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-neutral-300 px-4 py-10 text-center text-sm text-neutral-400">
          Nothing reviewed yet
        </div>
      ) : (
        <ul className="space-y-3">
          {groups.map((g) => (
            <GroupCard key={g.channel} g={g} onOpen={onOpen} />
          ))}
        </ul>
      )}

      {rejected > 0 && <p className="text-xs text-neutral-400">{rejected} rejected · not executed</p>}
      <ExecutedList list={executions} />
    </aside>
  );
}
