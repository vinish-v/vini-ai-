/// <reference types="vite/client" />

import type { ViniApi } from "../preload/index";

declare global {
  interface Window {
    vini: ViniApi;
  }
}

