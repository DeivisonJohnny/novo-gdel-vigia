import type { HTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export function Tabela({ className, ...props }: HTMLAttributes<HTMLTableElement>) {
  return (
    <div className="rolagem overflow-x-auto">
      <table className={cn("w-full text-left text-sm", className)} {...props} />
    </div>
  );
}

export function Th({ className, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return <th className={cn("whitespace-nowrap border-b bg-elevada/60 px-4 py-2.5 text-xs font-medium text-suave", className)} {...props} />;
}

export function Td({ className, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("border-b px-4 py-3 align-middle", className)} {...props} />;
}

export function Tr({ className, clicavel, ...props }: HTMLAttributes<HTMLTableRowElement> & { clicavel?: boolean }) {
  return <tr className={cn("transition-colors", clicavel && "cursor-pointer hover:bg-elevada/70", className)} {...props} />;
}
