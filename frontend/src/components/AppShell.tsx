import { useState } from "react";
import { Outlet } from "react-router-dom";

import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export function AppShell() {
  const [navOpen, setNavOpen] = useState(false);
  return (
    <div className={`app-shell${navOpen ? " nav-open" : ""}`}>
      <TopBar onToggleNav={() => setNavOpen((open) => !open)} />
      <div className="app-body">
        <Sidebar onNavigate={() => setNavOpen(false)} />
        <main className="app-content" id="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
