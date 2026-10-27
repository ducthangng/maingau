import { Link, useParams } from "react-router-dom";
import ActionsTab from "../components/service/ActionsTab";
import JourneyTab from "../components/service/JourneyTab";
import ProfileTab from "../components/service/ProfileTab";
import CustomerList from "../components/service/CustomerList";
import ServiceStrip from "../components/service/ServiceStrip";
import { CustomerSearch } from "../components/service/ViewSwitch";
import { loadCard, loadIndex, useLoad } from "../lib/data";

// Customer 360° dashboard for a service agent on a call (prompts/ui-customer360.md §3).
// Start page: all customers, filtered by ID. Customer page: the strip, then profile, journey and
// next best actions side by side, so the agent never has to switch tabs while talking.
const COLUMNS = [
  { id: "profile", label: "Profile", Body: ProfileTab },
  { id: "journey", label: "Customer journey", Body: JourneyTab },
  { id: "actions", label: "Next best actions", Body: ActionsTab },
] as const;

function Landing() {
  const index = useLoad(loadIndex, []);
  if (index.status === "loading") return <p className="py-12 text-center text-neutral-500">Loading customers…</p>;
  if (index.status === "error") return <p className="text-red-700">Could not load index.json: {index.error}</p>;
  return <CustomerList rows={index.data} />;
}

function CustomerView({ id }: { id: string }) {
  const card = useLoad(() => loadCard(id), [id]);
  if (card.status === "loading") return <p className="py-12 text-center text-neutral-500">Loading {id}…</p>;
  if (card.status === "error")
    return (
      <div className="mx-auto max-w-xl space-y-4 py-12 text-center">
        <p className="text-neutral-700">
          {card.error === "Unknown customer" ? `No customer ${id}.` : `Could not load ${id}: ${card.error}`}
        </p>
        <div className="flex justify-center">
          <CustomerSearch autoFocus size="lg" />
        </div>
      </div>
    );
  const c = card.data;

  return (
    <div className="space-y-5">
      <Link to="/service" className="text-sm text-neutral-500 hover:text-neutral-900">
        ← All customers
      </Link>
      <ServiceStrip card={c} />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.6fr)]">
        {COLUMNS.map(({ id: col, label, Body }) => (
          <section key={col} aria-label={label} className="min-w-0 rounded-xl border border-neutral-200 bg-neutral-50/60 p-4">
            <h2 className="mb-3 text-sm font-semibold text-neutral-900">{label}</h2>
            <div className="xl:max-h-[calc(100vh-17rem)] xl:overflow-y-auto xl:pr-1">
              <Body card={c} />
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

export default function Service() {
  const { id } = useParams();
  if (!id) return <Landing />;
  const cid = decodeURIComponent(id).toUpperCase();
  return <CustomerView key={cid} id={cid} />;
}
