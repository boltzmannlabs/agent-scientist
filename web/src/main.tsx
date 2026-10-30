import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import "./index.css";
import App from "./App";
import { BrandEntrance } from "./components/BrandEntrance";
import { SystemActionsProvider } from "./contexts/SystemActions";
import { I18nProvider } from "./i18n";
import { exposePluginSDK } from "./plugins";
import { ThemeProvider } from "./themes";
import { SCI_BASE_PATH } from "./lib/api";

// Expose the plugin SDK before rendering so plugins loaded via <script>
// can access React, components, etc. immediately.
exposePluginSDK();

createRoot(document.getElementById("root")!).render(
  <BrowserRouter basename={SCI_BASE_PATH || undefined}>
    <I18nProvider>
      <ThemeProvider>
        <SystemActionsProvider>
          <BrandEntrance><App /></BrandEntrance>
        </SystemActionsProvider>
      </ThemeProvider>
    </I18nProvider>
  </BrowserRouter>,
);
