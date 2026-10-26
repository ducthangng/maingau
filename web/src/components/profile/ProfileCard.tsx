import type { CustomerCard } from "../../types/contracts";
import { ConsentPanel } from "./Consent";
import { FatiguePanel } from "./Fatigue";
import { ProfileHeader, TriageBanner } from "./Header";
import { ProductGrid } from "./Products";
import { Highlights, SignalChips } from "./Signals";
import { Timeline } from "./Timeline";
import { TrendsPanel } from "./Trends";
import { ValueRiskPanel } from "./ValueRisk";

export interface ProfileCardProps {
  card: CustomerCard;
  /** Signal chip currently selected (highlights the NBAs it drives on the right). */
  activeSignal: string | null;
  onSignalClick: (signalId: string) => void;
}

/**
 * Left card: "Who is this customer, and how are they changing?" (README §4.1 A1–A5, B1–B4).
 * Display only: every value comes from the card JSON; nothing is recomputed here.
 * Jump targets (data-ui-ref): header, value, consent:<type>, exclusion:<rule_id>, product:<line>,
 * product:service, signal:<id>, timeline:<id>, trend:<name>.
 */
export default function ProfileCard({ card, activeSignal, onSignalClick }: ProfileCardProps) {
  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <ProfileHeader card={card} />
        <TriageBanner card={card} sources={card.sources} />
      </div>
      <ConsentPanel card={card} />
      <ValueRiskPanel card={card} />
      <ProductGrid card={card} />
      <Highlights card={card} />
      <SignalChips card={card} activeSignal={activeSignal} onSignalClick={onSignalClick} />
      <Timeline card={card} />
      <TrendsPanel card={card} />
      <FatiguePanel card={card} />
    </div>
  );
}
