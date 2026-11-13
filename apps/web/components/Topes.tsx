"use client";

import Link from "next/link";
import type { Tope } from "@/lib/api";
import { monto } from "@/lib/format";
import { IconoCat, cx } from "./ui";

const pesos = (v: string | number) => monto(Math.round(Number(v)));
export const COLOR_ESTADO = { ok: "var(--ok)", cerca: "var(--warn)", pasado: "var(--danger)", sin_tope: "var(--line-strong)" } as const;

/** Una barra de tope: cuánto llevás, cuánto queda y si a este ritmo te pasás. */
export function BarraTope({ t, compacta }: { t: Tope; compacta?: boolean }) {
  const tope = Number(t.tope ?? 0);
  const pct = tope ? Math.min(100, (Number(t.gastado) / tope) * 100) : 0;
  const proy = tope ? Math.min(100, (Number(t.proyeccion) / tope) * 100) : 0;
  const texto =
    t.estado === "pasado" ? `Te pasaste ${pesos(Number(t.gastado) - tope)}`
      : `Te quedan ${pesos(t.queda)}${Number(t.proyeccion) > tope ? ` · a este ritmo cerrás en ${pesos(t.proyeccion)}` : ""}`;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline gap-2">
        <IconoCat icono={t.icono} color={t.color} size={compacta ? 26 : 30} />
        <span className="min-w-0 flex-1 truncate text-[14px] font-bold">{t.categoria}</span>
        <span className="num shrink-0 text-[13px] font-bold">
          {pesos(t.gastado)} <span className="font-semibold text-faint">/ {pesos(tope)}</span>
        </span>
      </div>
      <div className="relative h-2 overflow-hidden rounded-full bg-surface-2" aria-label={`${t.porcentaje}% del tope`}>
        {proy > pct && <div className="absolute inset-y-0 left-0 rounded-full opacity-25" style={{ width: `${proy}%`, background: COLOR_ESTADO[t.estado] }} />}
        <div className="suave absolute inset-y-0 left-0 rounded-full" style={{ width: `${Math.max(2, pct)}%`, background: COLOR_ESTADO[t.estado] }} />
      </div>
      <span className={cx("text-[12px] font-semibold", t.estado === "pasado" ? "text-danger" : t.estado === "cerca" ? "text-warn-ink" : "text-muted")}>{texto}</span>
    </div>
  );
}

/** Tarjeta de Inicio con los topes del mes. */
export function TopesCard({ topes }: { topes: Tope[] }) {
  return (
    <div className="flex flex-col gap-4 rounded-[22px] bg-surface p-4 shadow-soft">
      {topes.slice(0, 5).map((t) => <BarraTope key={t.categoria_id} t={t} compacta />)}
      {topes.length > 5 && <Link href="/topes" className="text-sm font-bold text-accent">Ver los {topes.length}</Link>}
    </div>
  );
}
