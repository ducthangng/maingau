import type { ReactNode } from "react";
import { TriangleAlert } from "lucide-react";
import { Bar, BarChart, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { CustomerCard } from "../../types/contracts";
import type { Range, TypedTrends } from "../../types/trends";
import { NOT_ENOUGH, eur, isMissing, pct } from "../../lib/format";
import { Sourced, sourceTitle } from "../Source";
import { Section } from "../Chips";
import { CHART, REF_CLS, humanize, num, type Sources } from "./shared";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const monthLabel = (m: string) => MONTHS[Number(m.slice(5, 7)) - 1] ?? m;

const TOOLTIP_STYLE = {
  contentStyle: { fontSize: 12, borderRadius: 8, border: "1px solid #e5e5e5", padding: "4px 8px" },
  labelStyle: { color: "#525252", fontWeight: 600 },
  cursor: { fill: "rgba(0,0,0,0.04)" },
};

const AXIS = { tick: { fontSize: 10, fill: CHART.axis }, tickLine: false, axisLine: false } as const;

function rangeText(r: Range | null | undefined, fallback = "no date range") {
  return r ? `${r.from} – ${r.to}` : fallback;
}

/** One trend block: title, real date range, source tooltip, notes. Null trend -> "not enough data". */
function TrendBlock({
  name,
  title,
  trend,
  sources,
  children,
  rangeFallback,
}: {
  name: string;
  title: string;
  rangeFallback?: string;
  trend: { src: string; range: Range | null; notes: string[] } | null;
  sources: Sources;
  children?: ReactNode;
}) {
  if (!trend) {
    return (
      <div data-ui-ref={`trend:${name}`} className={`${REF_CLS} flex items-baseline justify-between gap-2 px-1 py-1 text-sm`}>
        <span className="text-neutral-600">{title}</span>
        <span className="text-xs text-neutral-400 italic">{NOT_ENOUGH}</span>
      </div>
    );
  }
  return (
    <div data-ui-ref={`trend:${name}`} className={`${REF_CLS} rounded-lg border border-neutral-200 p-3`}>
      <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-x-2">
        <span className="text-sm font-medium">{title}</span>
        <span title={sourceTitle(trend.src, null, sources)} className="cursor-help text-[11px] tabular-nums text-neutral-500">
          {rangeText(trend.range, rangeFallback)}
        </span>
      </div>
      {children}
      {trend.notes?.length > 0 && (
        <ul className="mt-1.5 space-y-0.5">
          {trend.notes.map((n) => (
            <li key={n} className="text-[11px] leading-snug text-neutral-400">
              {n}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Stat({ label, src, sources, children, warn = false }: { label: string; src: string; sources: Sources; children: ReactNode; warn?: boolean }) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] text-neutral-500">{label}</div>
      <div className={`text-sm font-semibold tabular-nums ${warn ? "flex items-center gap-1 text-neutral-900" : ""}`}>
        {warn && <TriangleAlert className="size-3.5 shrink-0 text-neutral-500" aria-label="warning" />}
        <Sourced src={src} sources={sources}>
          {children}
        </Sourced>
      </div>
    </div>
  );
}

function ChargingChart({ t, s }: { t: NonNullable<TypedTrends["charging"]>; s: Sources }) {
  const data = t.months.map((m) => ({ ...m, label: monthLabel(m.month) }));
  const marker = (t.markers ?? [])[0];
  const markerMonth = marker ? data.find((d) => d.month === marker.date.slice(0, 7))?.label : undefined;
  const failures = Object.entries(t.failures_by_reason ?? {});
  return (
    <>
      <div className="text-[11px] text-neutral-500">kWh charged per month</div>
      <div className="h-24" title={sourceTitle(`${t.src}.energy_kwh`, null, s)}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 14, right: 4, bottom: 0, left: -24 }}>
            <XAxis dataKey="label" {...AXIS} />
            <YAxis {...AXIS} width={48} />
            <Tooltip {...TOOLTIP_STYLE} formatter={(v: number) => [`${num(v, 1)} kWh`, "charged"]} />
            {markerMonth && (
              <ReferenceLine
                x={markerMonth}
                stroke={CHART.axis}
                strokeDasharray="3 3"
                label={{ value: "AC price cut", position: "top", fontSize: 10, fill: "#737373" }}
              />
            )}
            <Bar dataKey="kwh" fill={CHART.accent} radius={[3, 3, 0, 0]} maxBarSize={28} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-xs text-neutral-600">
        <span className="text-neutral-500">Failed sessions</span>
        {t.months.map((m) => (
          <span key={m.month} className={m.failed > 0 ? "font-medium text-red-700" : ""}>
            {monthLabel(m.month)}{" "}
            <Sourced src={`${t.src}.status`} sources={s}>
              {num(m.failed)}
            </Sourced>
          </span>
        ))}
      </div>
      {failures.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1">
          {failures.map(([reason, n]) => (
            <span key={reason} className="rounded bg-red-50 px-1.5 py-px text-[11px] text-red-700">
              {humanize(reason)}{" "}
              <Sourced src={`${t.src}.failure_reason`} sources={s}>
                {num(n)}
              </Sourced>
            </span>
          ))}
        </div>
      )}
      {marker && (
        <p className="mt-1 text-[11px] text-neutral-500">
          ┆ {marker.date}: {marker.label}
        </p>
      )}
    </>
  );
}

function PortalChart({ t, s }: { t: NonNullable<TypedTrends["portal"]>; s: Sources }) {
  const data = t.months.map((m) => ({ ...m, label: monthLabel(m.month) }));
  const sum = (k: "offers" | "tariff_overview" | "consumption_chart") => t.months.reduce((a, m) => a + (m[k] ?? 0), 0);
  return (
    <>
      <div className="text-[11px] text-neutral-500">Sessions per month</div>
      <div className="h-20" title={sourceTitle(`${t.src}.session_start`, null, s)}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 6, right: 4, bottom: 0, left: -24 }}>
            <XAxis dataKey="label" {...AXIS} />
            <YAxis {...AXIS} width={48} allowDecimals={false} />
            <Tooltip
              {...TOOLTIP_STYLE}
              content={({ active, payload }) => {
                const d = active && payload?.[0]?.payload;
                if (!d) return null;
                return (
                  <div className="rounded-lg border border-neutral-200 bg-white px-2 py-1 text-xs shadow-sm">
                    <div className="font-semibold text-neutral-700">{d.month}</div>
                    <div>{d.sessions} sessions</div>
                    <div className="text-neutral-500">
                      offers {d.offers} · tariff overview {d.tariff_overview} · consumption chart {d.consumption_chart}
                    </div>
                  </div>
                );
              }}
            />
            <Bar dataKey="sessions" fill={CHART.accent} radius={[3, 3, 0, 0]} maxBarSize={28} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 text-xs text-neutral-600">
        <span className="text-neutral-500">Page views in range</span>
        {(["offers", "tariff_overview", "consumption_chart"] as const).map((k) => (
          <span key={k}>
            {humanize(k)}{" "}
            <Sourced src={`${t.src}.pages_viewed`} sources={s}>
              <span className="font-medium">{num(sum(k))}</span>
            </Sourced>
          </span>
        ))}
      </div>
    </>
  );
}

function NewsletterStats({ t, s }: { t: NonNullable<TypedTrends["newsletter"]>; s: Sources }) {
  const clicks = Object.entries(t.clicks_by_target ?? {});
  return (
    <>
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
        <Stat label="Delivered" src={`${t.src}.delivered`} sources={s}>
          {num(t.delivered)}
        </Stat>
        <Stat label="Real opens" src={`${t.src}.opened`} sources={s}>
          {num(t.real_opens)}
        </Stat>
        <Stat label="Clicks" src={`${t.src}.clicked`} sources={s}>
          {num(t.clicks)}
        </Stat>
        <Stat label="Prefetch excl." src={`${t.src}.open_client_class`} sources={s}>
          {num(t.prefetch_opens_excluded)}
        </Stat>
        <Stat label="Unsubscribed" src={`${t.src}.unsubscribed`} sources={s} warn={t.unsubscribed}>
          {t.unsubscribed ? "yes" : "no"}
        </Stat>
      </div>
      {clicks.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1 text-[11px] text-neutral-600">
          {clicks.map(([target, n]) => (
            <span key={target} className="rounded bg-neutral-100 px-1.5 py-px">
              {humanize(target)}{" "}
              <Sourced src={`${t.src}.click_target`} sources={s}>
                {num(n)}
              </Sourced>
            </span>
          ))}
        </div>
      )}
    </>
  );
}

function ServiceStats({ t, s }: { t: NonNullable<TypedTrends["service"]>; s: Sources }) {
  const max = Math.max(1, ...t.quarters.map((q) => q.tickets));
  return (
    <>
      <div className="flex items-end gap-1.5" title={sourceTitle(`${t.src}.created_at`, null, s)}>
        {t.quarters.map((q) => (
          <div key={q.quarter} className="flex min-w-0 flex-1 flex-col items-center gap-0.5">
            <span className="text-[11px] tabular-nums text-neutral-600">{q.tickets}</span>
            <div className="flex h-10 w-full items-end justify-center">
              <div
                className={`w-full max-w-7 rounded-t ${q.tickets > 0 ? "bg-accent-500" : "bg-neutral-100"}`}
                style={{ height: `${q.tickets > 0 ? Math.max(12, (q.tickets / max) * 100) : 6}%` }}
              />
            </div>
            <span className="text-[10px] text-neutral-400">{q.quarter.replace("-", " ")}</span>
          </div>
        ))}
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Open tickets" src={`${t.src}.status`} sources={s} warn={t.open > 0}>
          {num(t.open)}
        </Stat>
        <Stat label="Repeat contacts" src={`${t.src}.repeat_contact`} sources={s}>
          {num(t.repeat_contacts)}
        </Stat>
        <Stat label="Latest CSAT" src={`${t.src}.csat`} sources={s} warn={!!t.latest_csat && t.latest_csat.v <= 2}>
          {t.latest_csat ? (
            <>
              {num(t.latest_csat.v)}/5 <span className="text-[11px] font-normal text-neutral-500">{t.latest_csat.date}</span>
            </>
          ) : (
            <span className="font-normal text-neutral-400 italic">{NOT_ENOUGH}</span>
          )}
        </Stat>
        <Stat label="Goodwill" src={`${t.src}.goodwill_eur`} sources={s}>
          {eur(t.goodwill_eur)}
        </Stat>
      </div>
    </>
  );
}

function MobileUsageBar({ t, s }: { t: NonNullable<TypedTrends["mobile_usage"]>; s: Sources }) {
  const share = t.usage_share;
  const width = isMissing(share) ? 0 : Math.min(100, Math.max(0, share * 100));
  return (
    <>
      <div className="mb-1 flex items-baseline justify-between text-xs text-neutral-600">
        <span>
          {t.plan ?? NOT_ENOUGH} · avg{" "}
          <Sourced src={`${t.src}.avg_data_used_gb_3m`} sources={s}>
            <span className="font-semibold text-neutral-900">{isMissing(t.avg_data_used_gb_3m) ? NOT_ENOUGH : `${num(t.avg_data_used_gb_3m, 1)} GB`}</span>
          </Sourced>{" "}
          of{" "}
          <Sourced src={`${t.src}.data_volume_gb`} sources={s}>
            {isMissing(t.data_volume_gb) ? NOT_ENOUGH : `${num(t.data_volume_gb)} GB`}
          </Sourced>
        </span>
        <Sourced src={`${t.src}.avg_data_used_gb_3m`} sources={s}>
          {pct(share, 0)}
        </Sourced>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-neutral-100"
        role="meter"
        aria-label="Data used vs limit"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(width)}
      >
        <div className={`h-full rounded-full ${width >= 90 ? "bg-red-500" : "bg-accent-500"}`} style={{ width: `${width}%` }} />
      </div>
      <div className="mt-1 text-[11px] text-neutral-500">
        Limit reached{" "}
        <Sourced src={`${t.src}.data_limit_reached_3m`} sources={s}>
          {isMissing(t.data_limit_reached_3m) ? NOT_ENOUGH : `${num(t.data_limit_reached_3m)} of the last 3 months`}
        </Sourced>
      </div>
    </>
  );
}

function HemsSummary({ t, s }: { t: NonNullable<TypedTrends["hems"]>; s: Sources }) {
  const daily = t.daily ?? [];
  const data = daily.map((d) => ({ date: d.date.slice(8, 10), rate: d.self_consumption_rate }));
  // An aggregate with no daily observation behind it (e.g. no heat-pump telemetry) is "not enough data", never 0.
  const kwh = (key: "grid_export_kwh" | "heat_pump_kwh" | "ev_charging_kwh") => {
    const v = t[key] as number | null | undefined;
    if (isMissing(v) || !daily.some((d) => !isMissing(d[key]))) return <span className="font-normal italic text-neutral-400">{NOT_ENOUGH}</span>;
    return `${num(v)} kWh`;
  };
  return (
    <>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Self-consumption" src={`${t.src}.self_consumption_rate`} sources={s}>
          {pct(t.self_consumption_rate_avg, 0)}
        </Stat>
        <Stat label="Grid export" src={`${t.src}.grid_export_kwh`} sources={s}>
          {kwh("grid_export_kwh")}
        </Stat>
        <Stat label="Heat pump" src={`${t.src}.heat_pump_kwh`} sources={s}>
          {kwh("heat_pump_kwh")}
        </Stat>
        <Stat label="EV charging" src={`${t.src}.ev_charging_kwh`} sources={s}>
          {kwh("ev_charging_kwh")}
        </Stat>
      </div>
      {data.length > 1 && (
        <>
          <div className="mt-2 text-[11px] text-neutral-500">Daily self-consumption rate</div>
          <div className="h-14" title={sourceTitle(`${t.src}.self_consumption_rate`, null, s)}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
                <XAxis dataKey="date" hide />
                <YAxis hide domain={[0, 1]} />
                <Tooltip
                  {...TOOLTIP_STYLE}
                  cursor={{ stroke: CHART.grid }}
                  labelFormatter={(l) => `Sep ${l}`}
                  formatter={(v: number) => [pct(v, 0), "self-consumption"]}
                />
                <Line type="monotone" dataKey="rate" stroke={CHART.accent} strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
      <div className="mt-1 text-[11px] text-neutral-500">
        Days with data{" "}
        <Sourced src={`${t.src}.date`} sources={s}>
          {num(t.days_with_data)}
        </Sourced>
        {" · missing "}
        <Sourced src={`${t.src}.date`} sources={s}>
          <span className={t.days_missing > 0 ? "font-medium text-neutral-900" : ""}>{num(t.days_missing)}</span>
        </Sourced>
      </div>
    </>
  );
}

/** B (trends): compact mini charts, each with its real date range. Never a CLV trend. */
export function TrendsPanel({ card }: { card: CustomerCard }) {
  const s = card.sources;
  const t = (card.profile.trends ?? {}) as unknown as Partial<TypedTrends>;
  const charging = t.charging ?? null;
  const portal = t.portal ?? null;
  const newsletter = t.newsletter ?? null;
  const service = t.service ?? null;
  const mobile = t.mobile_usage ?? null;
  const hems = t.hems ?? null;

  // Trends with data first; the "not enough data" lines collect at the bottom.
  const blocks: { key: string; has: boolean; node: ReactNode }[] = [
    {
      key: "service",
      has: !!service,
      // product:service is a path target (P-SV-01); the service trend is the closest thing to a "service" product.
      node: (
        <div data-ui-ref="product:service" className={REF_CLS}>
          <TrendBlock name="service" title="Service" trend={service} sources={s}>
            {service && <ServiceStats t={service} s={s} />}
          </TrendBlock>
        </div>
      ),
    },
    {
      key: "charging",
      has: !!charging,
      node: (
        <TrendBlock name="charging" title="Charging" trend={charging} sources={s}>
          {charging && <ChargingChart t={charging} s={s} />}
        </TrendBlock>
      ),
    },
    {
      key: "portal",
      has: !!portal,
      node: (
        <TrendBlock name="portal" title="Portal" trend={portal} sources={s}>
          {portal && <PortalChart t={portal} s={s} />}
        </TrendBlock>
      ),
    },
    {
      key: "newsletter",
      has: !!newsletter,
      node: (
        <TrendBlock name="newsletter" title="Newsletter" trend={newsletter} sources={s}>
          {newsletter && <NewsletterStats t={newsletter} s={s} />}
        </TrendBlock>
      ),
    },
    {
      key: "mobile_usage",
      has: !!mobile,
      node: (
        <TrendBlock name="mobile_usage" title="Mobile data usage" trend={mobile} sources={s} rangeFallback="3-month aggregate, no trend">
          {mobile && <MobileUsageBar t={mobile} s={s} />}
        </TrendBlock>
      ),
    },
    {
      key: "hems",
      has: !!hems,
      node: (
        <TrendBlock name="hems" title="HEMS (September only)" trend={hems} sources={s}>
          {hems && <HemsSummary t={hems} s={s} />}
        </TrendBlock>
      ),
    },
  ];
  const withData = blocks.filter((b) => b.has);
  const empty = blocks.filter((b) => !b.has);

  return (
    <Section title="Trends">
      <div className="space-y-2">
        <p className="rounded-lg bg-neutral-50 px-3 py-1.5 text-xs text-neutral-600" title={t.clv_note ?? undefined}>
          <span className="font-medium text-neutral-800">CLV is a single snapshot — no CLV trend.</span>
          {t.clv_note ? <span className="text-neutral-400"> ({t.clv_note})</span> : null}
        </p>
        {withData.map((b) => (
          <div key={b.key}>{b.node}</div>
        ))}
        {empty.length > 0 && (
          <div className="divide-y divide-neutral-100 rounded-lg border border-dashed border-neutral-200 px-2 py-0.5">
            {empty.map((b) => (
              <div key={b.key}>{b.node}</div>
            ))}
          </div>
        )}
      </div>
    </Section>
  );
}
