import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { REJECT_REASONS, type ReasonCode } from "../../lib/decisions";
import { OVERRIDE_REASONS, RejectBar, RejectReasonSelect, whyCode, type RejectWhy } from "./NbaPanel";

// The reject control of the decision box (orchestration pop-up and Customer 360° actions tab):
// a reason from the list is required, the note is optional, and overrides carry a code too.

const noop = () => {};
const bar = (why: RejectWhy) => renderToStaticMarkup(<RejectBar why={why} onChange={noop} onReject={noop} onCancel={noop} />);
const rejectButton = (html: string) => html.match(/<button[^>]*>Reject<\/button>/)?.[0] ?? "";

describe("reject control", () => {
  it("cannot submit without a reason, even with a note", () => {
    expect(rejectButton(bar({ code: "", note: "" }))).toContain('disabled=""');
    expect(rejectButton(bar({ code: "", note: "customer said no" }))).toContain('disabled=""');
  });

  it("can submit once a reason is picked; the note stays optional", () => {
    const button = rejectButton(bar({ code: "no_time", note: "" }));
    expect(button).not.toBe("");
    expect(button).not.toContain('disabled=""');
  });

  it("lists the eight reasons in plain words and starts on the prompt", () => {
    const html = renderToStaticMarkup(<RejectReasonSelect value="" onChange={noop} />);
    expect(html).toMatch(/<option value="" disabled="" selected="">Why reject\?<\/option>/);
    for (const [code, label] of Object.entries(REJECT_REASONS)) {
      expect(html).toContain(`<option value="${code}">${label}</option>`);
    }
    const visible = html.replace(/<[^>]+>/g, " ");
    expect(visible).not.toMatch(/_/); // engine codes stay in the value, not in the text
  });
});

describe("override reasons", () => {
  it("map each preset to a reason code", () => {
    const why = (preset: string) => whyCode({ preset, note: "" });
    expect(why("Better channel for this customer")).toBe("wrong_channel");
    expect(why("More relevant right now")).toBe("not_relevant");
    expect(why("Customer asked for this")).toBe("other");
    expect(why("Other")).toBe("other");
    expect(why("Recent talk with the customer")).toBe("wrong_timing");
    const codes = Object.keys(REJECT_REASONS) as ReasonCode[];
    for (const code of Object.values(OVERRIDE_REASONS)) expect(codes).toContain(code);
  });
});
