import "@fontsource-variable/archivo/standard.css"; // headings (wide), self-hosted
import "@fontsource-variable/hanken-grotesk/index.css"; // body text, self-hosted
import "./styles.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
