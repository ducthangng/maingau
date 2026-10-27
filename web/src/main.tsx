import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./index.css";
import { settleKnownOutcomes } from "./lib/outcomes";

// A campaign fast-forwarded before its decisions were settled: settle them, so customers show their new proposal.
settleKnownOutcomes();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
