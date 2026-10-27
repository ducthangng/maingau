import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  Customer360Skeleton,
  CustomerListSkeleton,
  CustomerModalSkeleton,
  CustomerSkeleton,
  GroupsSkeleton,
  JourneySkeleton,
  OverviewSkeleton,
  WorklistSkeleton,
} from "./Skeleton";

// Loading skeletons: announced once to screen readers, and they never show anything that looks like data.

const visibleText = (html: string) =>
  html
    .replace(/<span class="sr-only">[^<]*<\/span>/g, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();

const CASES: [string, ReactElement, string, string[]][] = [
  ["overview", <OverviewSkeleton />, "Loading the overview…", ["#", "Action", "Customers", "Expected ΔCLV", "Main reason"]],
  ["worklist", <WorklistSkeleton />, "Loading the worklist…", []],
  ["groups", <GroupsSkeleton />, "Loading the groups…", []],
  ["customer list", <CustomerListSkeleton />, "Loading customers…", []],
  ["customer 360", <Customer360Skeleton id="MG-100068" />, "Loading MG-100068…", ["Profile", "Customer journey", "Next best actions"]],
  ["customer page", <CustomerSkeleton id="MG-100068" />, "Loading MG-100068…", []],
  ["customer modal", <CustomerModalSkeleton id="MG-100068" />, "Loading MG-100068…", []],
  ["journey", <JourneySkeleton />, "Loading the journey…", []],
];

describe("loading skeletons", () => {
  it.each(CASES)("%s: one status region with a label, and only real labels as visible text", (_, el, label, labels) => {
    const html = renderToStaticMarkup(el);
    expect(html.match(/role="status"/g)).toHaveLength(1);
    expect(html).toContain('aria-busy="true"');
    expect(html).toContain(`<span class="sr-only">${label}</span>`);
    expect(html).toContain("skeleton-reveal"); // fades in after 150 ms, so fast loads never flash
    expect(visibleText(html).split(" ").filter(Boolean)).toEqual(labels.join(" ").split(" ").filter(Boolean));
  });

  it("renders the same bones every time (no random widths)", () => {
    for (const [, el] of CASES) expect(renderToStaticMarkup(el)).toBe(renderToStaticMarkup(el));
  });

  it("index.html paints a header and an outline before the app loads, and React replaces it", () => {
    const html = readFileSync(fileURLToPath(new URL("../../index.html", import.meta.url)), "utf8");
    const root = html.slice(html.indexOf('<div id="root">'), html.indexOf("<noscript>"));
    expect(root).toContain("MAINGAU · Next Best Action");
    expect(root).toContain('role="status"');
    expect(html).toContain("prefers-reduced-motion");
  });
});
