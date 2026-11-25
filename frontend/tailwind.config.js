const cor = (nome) => `rgb(var(--${nome}) / <alpha-value>)`;

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ['"Geist Variable"', "ui-sans-serif", "system-ui", "sans-serif"] },
      colors: {
        fundo: cor("fundo"),
        superficie: cor("superficie"),
        elevada: cor("elevada"),
        borda: cor("borda"),
        texto: cor("texto"),
        suave: cor("suave"),
        fraco: cor("fraco"),
        primaria: cor("primaria"),
        "primaria-texto": cor("primaria-texto"),
        alerta: cor("alerta"),
        atencao: cor("atencao"),
        sucesso: cor("sucesso"),
        info: cor("info"),
        revisao: cor("revisao"),
      },
      boxShadow: { cartao: "0 1px 2px rgb(0 0 0 / 0.04), 0 4px 16px -8px rgb(0 0 0 / 0.12)" },
      keyframes: {
        pulso: { "0%, 100%": { opacity: "1" }, "50%": { opacity: "0.35" } },
        entrar: { from: { opacity: "0", transform: "translateY(4px)" }, to: { opacity: "1", transform: "none" } },
      },
      animation: { pulso: "pulso 1.6s ease-in-out infinite", entrar: "entrar 180ms ease-out" },
    },
  },
};
