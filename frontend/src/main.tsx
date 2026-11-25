import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import "@fontsource-variable/geist";
import "./index.css";
import { App } from "./App";
import { ProvedorSessao } from "./hooks/useSessao";
import { ErroApi } from "./lib/api";

const cliente = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5_000,
      refetchOnWindowFocus: true,
      retry: (tentativas, erro) => !(erro instanceof ErroApi && erro.status < 500) && tentativas < 2,
    },
  },
});

createRoot(document.getElementById("raiz")!).render(
  <StrictMode>
    <QueryClientProvider client={cliente}>
      <BrowserRouter>
        <ProvedorSessao>
          <App />
          <Toaster position="top-right" richColors closeButton theme="system" />
        </ProvedorSessao>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
