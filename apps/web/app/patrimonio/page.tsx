"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import useSWR from "swr";
import { Plus, ShieldCheck } from "lucide-react";
import { PatrimonioChart } from "@/components/Graficos";
import { InversionFila, InversionSheet, SelectorCotizacion, type InversionAbierta } from "@/components/Inversiones";
import { Boton, Esqueleto, Lista, Seccion, Titulo, cx } from "@/components/ui";
import type { Inversion, Patrimonio } from "@/lib/api";
import { fechaCorta, monto } from "@/lib/format";
import { useContador } from "@/lib/hooks";

const ORDEN_ACTIVOS = ["Pesos", "Dólares", "Inversiones", "Te deben"];
const ORDEN_PASIVOS = ["Tarjetas", "Préstamos", "Le debés"];
const COLOR: Record<string, string> = {
  Pesos: "#2f5bea", Dólares: "#1f8a5b", Inversiones: "#8b5cf6", "Te deben": "#0ea5a4",
  Tarjetas: "#e8762d", Préstamos: "#c2362b", "Le debés": "#d4a017",
};

function Barra({ grupos, total }: { grupos: [string, number][]; total: number }) {
  return (
    <div className="flex h-3 gap-[3px] overflow-hidden rounded-full bg-surface-2">
      {grupos.map(([g, v]) => <div key={g} className="suave h-full rounded-full" style={{ width: `${(v / Math.max(total, 1)) * 100}%`, background: COLOR[g] }} title={g} />)}
    </div>
  );
}

function Lado({ titulo, items, orden, total }: { titulo: string; items: Patrimonio["items"]; orden: string[]; total: number }) {
  const [abierto, setAbierto] = useState<string | null>(null);
  const grupos = orden.map((g) => [g, items.filter((i) => i.grupo === g).reduce((s, i) => s + Number(i.ars ?? 0), 0)] as [string, number]).filter(([, v]) => v > 0);
  if (!grupos.length) return null;
  return (
    <div className="flex flex-col gap-3 rounded-[22px] bg-surface p-5 shadow-soft">
      <div className="flex items-baseline justify-between">
        <span className="font-bold">{titulo}</span>
        <span className="num text-lg font-extrabold">{monto(Math.round(total))}</span>
      </div>
      <Barra grupos={grupos} total={total} />
      <div className="flex flex-col">
        {grupos.map(([g, v]) => (
          <div key={g}>
            <button className="flex w-full items-center gap-2.5 py-2 text-left text-sm" onClick={() => setAbierto(abierto === g ? null : g)} aria-expanded={abierto === g}>
              <i className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: COLOR[g] }} />
              <span className="flex-1 font-semibold">{g}</span>
              <span className="num font-bold">{monto(Math.round(v))}</span>
            </button>
            {abierto === g && (
              <div className="mb-2 ml-5 flex flex-col gap-1 rounded-xl bg-surface-2 p-3 text-[13px]">
                {items.filter((i) => i.grupo === g).map((i) => (
                  <Link key={i.nombre} href={i.ref} className="flex justify-between gap-3 hover:underline">
                    <span className="truncate">{i.nombre}</span>
                    <span className="num shrink-0 font-semibold">
                      {monto(i.moneda === "ARS" ? Math.round(Number(i.monto)) : i.monto, i.moneda)}
                      {i.moneda === "USD" && i.ars && <span className="font-normal text-muted"> · {monto(Math.round(Number(i.ars)))}</span>}
                    </span>
                  </Link>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function PatrimonioPage() {
  const { data: p } = useSWR<Patrimonio>("/patrimonio");
  const { data: inversiones } = useSWR<Inversion[]>("/inversiones");
  const [inv, setInv] = useState<InversionAbierta>(null);
  const neto = Number(p?.neto ?? 0);
  const animado = useContador(neto);
  const puntos = useMemo(() => (p?.serie ?? []).map((s) => ({ ...s, neto: Number(s.neto) })), [p]);

  if (!p) return <Esqueleto className="h-96 rounded-[28px]" />;
  const anterior = puntos.length > 1 ? puntos[puntos.length - 2] : null;
  const dif = anterior ? neto - anterior.neto : 0;
  const meses = p.meses_esencial ? Number(p.meses_esencial) : null;
  const c = p.cotizacion;

  return (
    <div className="flex flex-col gap-7">
      <Titulo>Patrimonio</Titulo>
      <div className="grid grid-cols-1 gap-7 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] lg:items-start lg:gap-10">
        <div className="flex min-w-0 flex-col gap-7">
          <section className="flex flex-col gap-4 rounded-[28px] bg-slab p-6 text-slab-ink shadow-soft lg:p-8">
            <div>
              <p className="text-sm text-slab-muted">Tu patrimonio neto</p>
              <p className="display num text-[clamp(44px,12vw,60px)] leading-[0.95] font-bold">{monto(Math.round(animado))}</p>
              {p.neto_usd && c.valor && (
                <p className="mt-2 text-sm text-slab-muted">
                  Son <b className="num text-slab-ink">{monto(p.neto_usd, "USD")}</b> al dólar {c.nombre} ({monto(c.valor)}{c.vieja ? ", última conocida" : ""}).
                </p>
              )}
              {anterior && Math.abs(dif) >= 1 && (
                <p className={cx("mt-1 text-sm font-semibold", dif > 0 ? "text-[#8ee0b5]" : "text-[#ffab73]")}>
                  {dif > 0 ? "▲" : "▼"} {monto(Math.abs(Math.round(dif)))} desde el {fechaCorta(anterior.fecha)}
                </p>
              )}
            </div>
            <p className="text-[13px] text-slab-muted">Todo lo que tenés (cuentas, dólares, inversiones, lo que te deben) menos todo lo que debés.</p>
          </section>

          {puntos.length > 1 ? (
            <Seccion titulo="Cómo viene">
              <div className="rounded-[22px] bg-surface p-5 shadow-soft">
                <PatrimonioChart puntos={puntos} />
                {puntos.some((x) => x.estimado) && <p className="mt-2 text-xs text-faint">Las barras claras son estimadas con los saldos de tus cuentas a fin de mes.</p>}
              </div>
            </Seccion>
          ) : (
            <p className="rounded-[20px] border border-dashed border-line-strong p-4 text-sm text-muted">
              Desde hoy guardo una foto de tu patrimonio cada vez que entrás acá. En unas semanas vas a ver cómo viene mes a mes.
            </p>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Lado titulo="Tenés" items={p.items.filter((i) => i.activo)} orden={ORDEN_ACTIVOS} total={Number(p.activos)} />
            <Lado titulo="Debés" items={p.items.filter((i) => !i.activo)} orden={ORDEN_PASIVOS} total={Number(p.pasivos)} />
          </div>
          {p.sin_convertir && <p className="text-xs text-warn-ink">Hay montos en dólares sin pasar a pesos: elegí una cotización abajo.</p>}
        </div>

        <div className="flex min-w-0 flex-col gap-7">
          {meses != null && (
            <section className={cx("flex gap-4 rounded-[22px] p-5", meses >= 3 ? "bg-ok-soft" : "bg-warn-soft")}>
              <ShieldCheck size={28} className={cx("shrink-0", meses >= 3 ? "text-ok" : "text-warn-ink")} />
              <div className="flex flex-col gap-1">
                <p className="font-extrabold">Fondo de emergencia: {String(meses).replace(".", ",")} {meses === 1 ? "mes" : "meses"}</p>
                <p className="text-sm text-muted">
                  Con lo que tenés a mano ({monto(Math.round(Number(p.liquido)))}, ya restadas las tarjetas) cubrís {String(meses).replace(".", ",")} meses de gastos fijos y cuotas
                  {p.meses_total && <>, o {String(Number(p.meses_total)).replace(".", ",")} de todo lo que gastás</>}.
                  {meses < 3 ? " Lo recomendable es tener entre 3 y 6." : meses < 6 ? " Vas bien: lo ideal es entre 3 y 6." : " Muy bien cubierto."}
                </p>
                {meses < 3 && <Link href="/metas" className="mt-1 w-fit text-sm font-bold text-accent">Armá una meta para eso</Link>}
              </div>
            </section>
          )}

          <Seccion titulo="Inversiones" extra={<Boton variante="linea" className="min-h-9 px-3" onClick={() => setInv({ nueva: true })}><Plus size={16} /> Agregar</Boton>}>
            {!inversiones ? (
              <Esqueleto className="h-32 rounded-[22px]" />
            ) : inversiones.length ? (
              <Lista>{inversiones.map((i) => <InversionFila key={i.id} i={i} onAbrir={() => setInv(i)} />)}</Lista>
            ) : (
              <p className="rounded-[20px] border border-dashed border-line-strong p-4 text-sm text-muted">
                Plazos fijos, fondos, cripto o acciones. Los plazos fijos calculan sus intereses solos y te aviso antes de que venzan.
              </p>
            )}
          </Seccion>

          <Seccion titulo="Dólar para convertir">
            <div className="rounded-[22px] bg-surface p-5 shadow-soft">
              <SelectorCotizacion c={c} />
              <p className="mt-3 text-xs text-faint">
                {c.manual ? "Usás una cotización fija." : c.valor ? `${c.nombre}: ${monto(c.valor)}${c.fecha ? `, actualizado ${new Date(c.fecha).toLocaleString("es-AR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false })}` : ""}. Fuente: DolarAPI.` : "No pude traer la cotización: cargala a mano."}
              </p>
            </div>
          </Seccion>
        </div>
      </div>
      <InversionSheet abierta={inv} onCerrar={() => setInv(null)} />
    </div>
  );
}
