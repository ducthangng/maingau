import { eur } from "../../lib/format";

/** Whole euros with a sign, in the app's euro style: "+€2,684". */
export function wholeEur(v: number): string {
  const r = Math.round(v);
  return r > 0 ? `+${eur(r)}` : r < 0 ? `−${eur(-r)}` : eur(0);
}
