import { Routes, Route, Link, Navigate } from "react-router-dom";
import Detail from "./pages/Detail";

function Landing() {
  return (
    <div className="app">
      <div className="topbar">
        <div className="crumbs">
          <span className="here">Surfaceome Viewer</span>
        </div>
      </div>
      <div style={{ padding: "60px 0" }}>
        <h1 className="symbol" style={{ fontSize: 64 }}>Surfaceome</h1>
        <p className="tldr" style={{ maxWidth: "60ch" }}>
          An annotated catalogue of human cell-surface proteins from seven
          public data sources. The viewer is in development — only{" "}
          <Link to="/gene/KAAG1" style={{ borderBottom: "1px dotted" }}>KAAG1</Link>{" "}
          has a full record so far.
        </p>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/gene/:symbol" element={<Detail />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
