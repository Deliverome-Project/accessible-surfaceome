import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { maybeRunPreflight } from "./lib/preflight";
import "./styles/tokens.css";
import "./styles/app.css";
import "./styles/findings.css";
import "./styles/tabs.css";
import "./styles/modality.css";
import "./styles/pill-tag-cite.css";
import "./styles/json-viewer.css";
import "./styles/export-menu.css";
import "./styles/tweaks.css";

async function bootstrap() {
  if (await maybeRunPreflight()) return;
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </React.StrictMode>,
  );
}

bootstrap();
