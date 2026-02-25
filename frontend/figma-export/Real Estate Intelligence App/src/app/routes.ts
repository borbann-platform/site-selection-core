import { createBrowserRouter } from "react-router";
import { Root } from "./pages/Root";
import { PropertyExplorer } from "./pages/PropertyExplorer";
import { AIChat } from "./pages/AIChat";
import { PropertyDetails } from "./pages/PropertyDetails";
import { Valuation } from "./pages/Valuation";
import { Districts } from "./pages/Districts";
import { SiteAnalysis } from "./pages/SiteAnalysis";
import { Settings } from "./pages/Settings";
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { DesignSystem } from "./pages/DesignSystem";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Root,
    children: [
      { index: true, Component: PropertyExplorer },
      { path: "chat", Component: AIChat },
      { path: "property/:id", Component: PropertyDetails },
      { path: "valuation", Component: Valuation },
      { path: "districts", Component: Districts },
      { path: "site-analysis", Component: SiteAnalysis },
      { path: "settings", Component: Settings },
      { path: "design-system", Component: DesignSystem },
    ],
  },
  { path: "/login", Component: Login },
  { path: "/register", Component: Register },
]);