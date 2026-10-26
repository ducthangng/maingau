// Shapes of profile.trends.* (free-form dicts in the contract). Written by nba/profile/trends.py;
// keep both in sync.
export interface Range {
  from: string;
  to: string;
}

interface TrendBase {
  src: string;
  range: Range | null;
  notes: string[];
}

export interface ChargingTrend extends TrendBase {
  months: { month: string; kwh: number; sessions: number; failed: number; ac_kwh: number; dc_kwh: number }[];
  failures_by_reason: Record<string, number>;
  markers: { date: string; label: string }[];
}

export interface PortalTrend extends TrendBase {
  months: { month: string; sessions: number; offers: number; tariff_overview: number; consumption_chart: number }[];
}

export interface NewsletterTrend extends TrendBase {
  delivered: number;
  real_opens: number;
  prefetch_opens_excluded: number;
  clicks: number;
  clicks_by_target: Record<string, number>;
  unsubscribed: boolean;
  months: { month: string; opens: number; clicks: number }[];
}

export interface ServiceTrend extends TrendBase {
  quarters: { quarter: string; tickets: number }[];
  open: number;
  repeat_contacts: number;
  latest_csat: { v: number; date: string; ticket_id: string } | null;
  goodwill_eur: number;
}

export interface MobileUsage extends TrendBase {
  contract_id: string;
  plan: string | null;
  data_volume_gb: number | null;
  avg_data_used_gb_3m: number | null;
  data_limit_reached_3m: number | null;
  usage_share: number | null;
}

export interface HemsTrend extends TrendBase {
  days_with_data: number;
  days_missing: number;
  self_consumption_rate_avg: number | null;
  grid_export_kwh: number;
  heat_pump_kwh: number;
  ev_charging_kwh: number;
  daily: { date: string; self_consumption_rate: number | null; grid_export_kwh: number | null; heat_pump_kwh: number | null; ev_charging_kwh: number | null }[];
}

export interface TypedTrends {
  charging: ChargingTrend | null;
  portal: PortalTrend | null;
  newsletter: NewsletterTrend | null;
  service: ServiceTrend | null;
  mobile_usage: MobileUsage | null;
  hems: HemsTrend | null;
  clv_note: string;
}
