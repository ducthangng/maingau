// Validate public/data/ against docs/schema/*.json, the same check README §8 asks for at M0.
// Works for the mock data and for the real export from `python -m nba.build --export web/public/data`.
import { readFileSync, readdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import Ajv from "ajv";

const here = dirname(fileURLToPath(import.meta.url));
const schemaDir = resolve(here, "../../docs/schema");
const dataDir = resolve(here, "../public/data");
const load = (path) => JSON.parse(readFileSync(path, "utf8"));

const ajv = new Ajv({ allErrors: true, strict: false });
const validator = (name) => ajv.compile(load(resolve(schemaDir, `${name}.schema.json`)));
const checkCard = validator("customer_card");
const checkRow = validator("index_row");
const checkSummary = validator("summary");

let failures = 0;
function report(label, ok, errors) {
  if (ok) return;
  failures += 1;
  console.error(`✗ ${label}`);
  for (const e of (errors ?? []).slice(0, 5)) console.error(`    ${e.instancePath || "/"} ${e.message}`);
}

const index = load(resolve(dataDir, "index.json"));
index.forEach((row, i) => report(`index.json[${i}] ${row.customer_id}`, checkRow(row), checkRow.errors));
report("summary.json", checkSummary(load(resolve(dataDir, "summary.json"))), checkSummary.errors);

const cardFiles = readdirSync(resolve(dataDir, "customers")).filter((f) => f.endsWith(".json"));
for (const file of cardFiles) {
  const card = load(resolve(dataDir, "customers", file));
  report(`customers/${file}`, checkCard(card), checkCard.errors);
  if (`${card.customer_id}.json` !== file) report(`customers/${file}: customer_id mismatch`, false, []);
}

const ids = new Set(index.map((r) => r.customer_id));
const missing = cardFiles.map((f) => f.replace(/\.json$/, "")).filter((id) => !ids.has(id));
if (missing.length) report(`cards without an index row: ${missing.join(", ")}`, false, []);
const noCard = [...ids].filter((id) => !cardFiles.includes(`${id}.json`));
if (noCard.length) report(`index rows without a card: ${noCard.join(", ")}`, false, []);

console.log(`${index.length} index rows, ${cardFiles.length} cards, ${failures} failures`);
process.exit(failures ? 1 : 0);
