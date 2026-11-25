export const PAPEIS = ["admin", "operador"] as const;

export type Papel = (typeof PAPEIS)[number];
