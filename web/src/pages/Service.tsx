import { Link, useParams, useSearchParams } from "react-router-dom";
import ActionsTab from "../components/service/ActionsTab";
import JourneyTab from "../components/service/JourneyTab";
import ProfileTab from "../components/service/ProfileTab";
import ServiceStrip from "../components/service/ServiceStrip";
import { CustomerSearch } from "../components/service/ViewSwitch";
import { mockName } from "../lib/customerMock";
import { loadCard, useLoad } from "../lib/data";

// Customer 360° dashboard for a service agent on a call (prompts/ui-customer360.md §3).
const TABS = [
  { id: "profile", label: "Profile" },
  { id: "journey", label: "Customer journey" },
  { id: "actions", label: "Next best actions" },
] as const;
type TabId = (typeof TABS)[number]["id"];

const EXAMPLES = ["MG-100186", "MG-100096", "MG-100023", "MG-100112", "MG-100026"];

function Landing() {
  return (
    <div className="mx-auto max-w-xl space-y-6 py-12 text-center">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Customer 360°</h1>
        <p className="mt-1 text-neutral-600">Type a customer ID to see who the customer is, what happened, and what to suggest.</p>
      </div>
      <div className="flex justify-center">
        <CustomerSearch autoFocus size="lg" />
      </div>
      <div className="flex flex-wrap justify-center gap-2 text-sm">
        {EXAMPLES.map((id) => (
          <Link key={id} to={`/service/${id}`} className="rounded-full bg-white px-3 py-1 text-neutral-700 ring-1 ring-neutral-200 hover:bg-neutral-50">
            {id} · {mockName(id)}
          </Link>
        ))}
      </div>
    </div>
  );
}

function CustomerView({ id }: { id: string }) {
  const card = useLoad(() => loadCard(id), [id]);
  const [params, setParams] = useSearchParams();
  const tab: TabId = TABS.some((t) => t.id === params.get("tab")) ? (params.get("tab") as TabId) : "profile";

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
      <ServiceStrip card={c} />
      <div className="flex gap-1 border-b border-neutral-200" role="tablist" aria-label="Customer 360°">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setParams({ tab: t.id }, { replace: true })}
            className={`-mb-px border-b-2 px-4 py-2 text-sm transition-colors duration-150 ${
              tab === t.id ? "border-neutral-900 font-medium text-neutral-900" : "border-transparent text-neutral-500 hover:text-neutral-800"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === "profile" && <ProfileTab card={c} />}
      {tab === "journey" && <JourneyTab card={c} />}
      {tab === "actions" && <ActionsTab card={c} />}
    </div>
  );
}

export default function Service() {
  const { id } = useParams();
  if (!id) return <Landing />;
  const cid = decodeURIComponent(id).toUpperCase();
  return <CustomerView key={cid} id={cid} />;
}
