import { useLayoutEffect, useRef } from "react";
import { Link, useParams } from "react-router-dom";
import type { CustomerCard } from "../types/contracts";
import ActionsTab from "../components/service/ActionsTab";
import JourneyTab from "../components/service/JourneyTab";
import ProfileTab from "../components/service/ProfileTab";
import CustomerList from "../components/service/CustomerList";
import ServiceColumn from "../components/service/ServiceColumn";
import ServiceStrip from "../components/service/ServiceStrip";
import { CustomerSearch } from "../components/service/ViewSwitch";
import { loadCard, loadIndex, useLoad } from "../lib/data";
import { Customer360Skeleton, CustomerListSkeleton } from "../components/Skeleton";

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
  if (index.status === "loading") return <CustomerListSkeleton />;
  if (index.status === "error") return <p className="text-red-700">Could not load index.json: {index.error}</p>;
  return <CustomerList rows={index.data} />;
}

function CustomerView({ id }: { id: string }) {
  const card = useLoad(() => loadCard(id), [id]);
  if (card.status === "loading") return <Customer360Skeleton id={id} />;
  if (card.status === "error")
    return (
      <div className="mx-auto max-w-xl space-y-4 py-12 text-center">
        <p className="text-neutral-700">
          {card.error === "Unknown customer" || card.error.endsWith("not JSON") ? `No customer ${id}.` : `Could not load ${id}: ${card.error}`}
        </p>
        <div className="flex justify-center">
          <CustomerSearch autoFocus size="lg" />
        </div>
      </div>
    );
  return <CustomerColumns card={card.data} />;
}

// Below lg one column; lg–xl Profile and Next best actions side by side, the journey full width
// below; from xl three columns that fill the screen (prompts/ui-polish.md §3.1).
const PLACE: Record<(typeof COLUMNS)[number]["id"], string> = {
  profile: "",
  journey: "lg:col-span-2 lg:order-last xl:col-span-1 xl:order-none",
  actions: "",
};

function CustomerColumns({ card: c }: { card: CustomerCard }) {
  const grid = useRef<HTMLDivElement>(null);

  // The columns reach to the bottom of the screen: measure where the grid starts (header and strip
  // can wrap) instead of guessing their height.
  useLayoutEffect(() => {
    const el = grid.current;
    if (!el) return;
    const set = () => {
      const top = el.getBoundingClientRect().top + window.scrollY;
      el.style.setProperty("--c360-h", `${Math.max(480, Math.round(window.innerHeight - top - 24))}px`);
    };
    set();
    const ro = new ResizeObserver(set);
    ro.observe(document.body);
    window.addEventListener("resize", set);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", set);
    };
  }, []);

  return (
    <div className="space-y-5">
      <Link to="/service" className="text-sm text-neutral-500 hover:text-neutral-900">
        ← All customers
      </Link>
      <ServiceStrip card={c} />
      <div
        ref={grid}
        className="grid gap-5 lg:grid-cols-2 xl:h-[var(--c360-h)] xl:grid-cols-[minmax(17rem,1fr)_minmax(17rem,1fr)_minmax(24rem,1.6fr)]"
      >
        {COLUMNS.map(({ id: col, label, Body }) => (
          <ServiceColumn key={col} label={label} className={PLACE[col]}>
            <Body card={c} />
          </ServiceColumn>
        ))}
      </div>
    </div>
  );
}

export default function Service() {
  const { id } = useParams();
  if (!id) return <Landing />;
  const cid = id.toUpperCase(); // useParams already decodes
  return <CustomerView key={cid} id={cid} />;
}
