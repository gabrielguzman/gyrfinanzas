"use client";

import Link from "next/link";
import { ArrowRight, ShoppingBag, Target, TriangleAlert } from "lucide-react";
import type { CalendarioPlan, Presupuesto } from "@/lib/api";
import { fechaCorta, monto } from "@/lib/format";
import { useContador } from "@/lib/hooks";
import { cx } from "./ui";

/** «Te quedan $X para 21 días, cobrás el 1 dic». */
export function fraseCiclo(p: Presupuesto): string {
  const dias = p.dias_restantes === 1 ? "1 día" : `${p.dias_restantes} días`;
  const cobro = p.proximo_cobro ? `, cobrás el ${fechaCorta(p.proximo_cobro)}` : "";
  const r = Number(p.restante);
  return r >= 0 ? `Te quedan ${monto(r)} para ${dias}${cobro}` : `Te pasaste ${monto(-r)} del mes y faltan ${dias}${cobro}`;
}

/** Tiempo del ciclo transcurrido contra plata del ciclo gastada. */
export function BarrasCiclo({ p, oscuro }: { p: Presupuesto; oscuro?: boolean }) {
  const tiempo = Math.min(100, ((p.dias_total - p.dias_restantes + 1) / Math.max(1, p.dias_total)) * 100);
  const para = Number(p.para_gastar);
  const plata = para > 0 ? Math.min(100, (Number(p.gastado) / para) * 100) : 100;
  const adelantado = plata > tiempo + 8;
  const fila = (label: string, pct: number, color: string) => (
    <div className="flex items-center gap-3">
      <span className={cx("w-24 shrink-0 text-xs font-semibold", oscuro ? "opacity-75" : "text-muted")}>{label}</span>
      <div className={cx("h-2 flex-1 overflow-hidden rounded-full", oscuro ? "bg-white/15" : "bg-surface-2")}>
        <div className="suave h-full rounded-full" style={{ width: `${Math.max(2, pct)}%`, background: color }} />
      </div>
      <span className={cx("num w-10 shrink-0 text-right text-xs font-bold", oscuro ? "" : "text-muted")}>{Math.round(pct)}%</span>
    </div>
  );
  return (
    <div className="flex flex-col gap-1.5" aria-label={`Pasó el ${Math.round(tiempo)}% del mes y gastaste el ${Math.round(plata)}% de lo que tenías para gastar`}>
      {fila("Pasó del mes", tiempo, oscuro ? "rgba(255,255,255,.75)" : "var(--faint)")}
      {fila("Gastaste", plata, adelantado ? "var(--warn)" : oscuro ? "#a9c1ff" : "var(--accent)")}
    </div>
  );
}

/** La tarjeta de Inicio: el número del día. */
export function HoyCard({ p, cal }: { p: Presupuesto | undefined; cal?: CalendarioPlan }) {
  const hoy = Number(p?.hoy ?? 0);
  const animado = useContador(Math.abs(hoy));
  if (!p) return <div className="esqueleto h-[150px] rounded-[24px]" />;

  if (!p.configurado) {
    return (
      <Link href="/plan" className="press flex items-center gap-4 rounded-[24px] border-2 border-dashed border-line-strong p-5">
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-accent-soft text-accent"><Target size={24} /></span>
        <span className="flex flex-1 flex-col">
          <span className="font-extrabold">¿Cuánto podés gastar hoy?</span>
          <span className="text-sm text-muted">Decime cuándo cobrás y cuánto, y te lo calculo cada día.</span>
        </span>
        <ArrowRight size={20} className="shrink-0 text-faint" />
      </Link>
    );
  }

  const pasado = hoy < 0;
  return (
    <div className="flex flex-col gap-2">
    <Link
      href="/plan"
      className={cx(
        "press flex flex-col gap-4 rounded-[24px] p-5 shadow-soft lg:p-6",
        pasado ? "bg-warn-soft text-warn-ink" : "bg-accent text-accent-ink"
      )}
      aria-label={`${pasado ? "Hoy te pasaste" : "Hoy podés gastar"} ${monto(Math.abs(hoy))}. ${fraseCiclo(p)}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold opacity-80">{pasado ? "Hoy te pasaste" : "Hoy podés gastar"}</p>
          <p className="display num text-[44px] leading-none font-bold">{monto(Math.round(animado))}</p>
        </div>
        <ArrowRight size={20} className="mt-1 shrink-0 opacity-70" />
      </div>
      <p className="text-sm font-semibold opacity-90">
        {fraseCiclo(p)}.
        {pasado && p.manana && Number(p.manana) > 0 && ` Si no gastás más hoy, mañana tenés ${monto(p.manana)}.`}
      </p>
      {!pasado && <BarrasCiclo p={p} oscuro />}
      {cal?.rojo && (
        <p className={cx("flex items-center gap-2 rounded-xl p-2.5 text-[13px] font-bold", pasado ? "bg-white/60" : "bg-white/15")}>
          <TriangleAlert size={16} className="shrink-0" />
          El {fechaCorta(cal.rojo.fecha)} tus cuentas quedarían en {monto(cal.rojo.saldo)}
        </p>
      )}
    </Link>
    <Link href="/comprar" className="press flex items-center justify-center gap-2 rounded-2xl border border-line-strong bg-surface py-2.5 text-sm font-bold">
      <ShoppingBag size={16} /> ¿Me lo puedo comprar?
    </Link>
    </div>
  );
}
