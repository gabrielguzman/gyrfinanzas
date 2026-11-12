"use client";

import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { Hash, Plane, Power } from "lucide-react";
import { limpiarEtiqueta, rango } from "@/components/EtiquetasEditor";
import { useApp } from "@/components/Shell";
import { Boton, Esqueleto, IconoCat, Seccion, Titulo, Vacio, inputCls } from "@/components/ui";
import { api, type Etiquetas, type EtiquetaResumen } from "@/lib/api";
import { monto } from "@/lib/format";


function Tarjeta({ e }: { e: EtiquetaResumen }) {
  const total = Number(e.total);
  return (
    <Link href={`/etiquetas/${e.nombre}`} className="press flex flex-col gap-3 rounded-[22px] bg-surface p-4 shadow-soft hover:bg-surface-2">
      <div className="flex items-start gap-3">
        <span data-cat="pink" className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px] bg-[var(--cat-bg)] text-[var(--cat-fg)]"><Hash size={20} /></span>
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="flex items-center gap-2 truncate font-extrabold">
            #{e.nombre}
            {e.activa && <span className="rounded-full bg-ok-soft px-2 py-0.5 text-[11px] font-bold text-ok">activa</span>}
          </span>
          <span className="text-[13px] text-muted">{rango(e)} · {e.cantidad} {e.cantidad === 1 ? "gasto" : "gastos"}</span>
        </span>
        <span className="flex flex-col items-end">
          <span className="num text-lg font-extrabold">{monto(Math.round(total))}</span>
          {Number(e.total_usd) > 0 && <span className="num text-[12px] font-bold text-muted">+ {monto(e.total_usd, "USD")}</span>}
        </span>
      </div>
      {total > 0 && (
        <div className="flex h-2 gap-[2px] overflow-hidden rounded-full" aria-hidden>
          {e.por_categoria.slice(0, 6).map((c) => (
            <span key={c.nombre} data-cat={c.color || "slate"} className="h-full bg-[var(--cat-fg)]" style={{ width: `${(Number(c.total) / total) * 100}%` }} />
          ))}
        </div>
      )}
      {e.por_categoria.length > 0 && (
        <span className="flex flex-wrap gap-x-3 gap-y-1 text-[12px] text-muted">
          {e.por_categoria.slice(0, 3).map((c) => (
            <span key={c.nombre} className="flex items-center gap-1"><IconoCat icono={c.icono} color={c.color} size={18} /> {c.nombre} <b className="num text-ink">{monto(Math.round(Number(c.total)))}</b></span>
          ))}
        </span>
      )}
    </Link>
  );
}

export default function EtiquetasPage() {
  const { data, mutate } = useSWR<Etiquetas>("/etiquetas");
  const { aviso } = useApp();
  const [nueva, setNueva] = useState("");

  async function activar(nombre: string | null) {
    mutate(await api.put<Etiquetas>("/etiquetas/activa", { nombre }), { revalidate: false });
    aviso(nombre ? `#${limpiarEtiqueta(nombre)} activa: todo lo que cargues la lleva` : "Etiqueta apagada");
    setNueva("");
  }

  if (!data) return <Esqueleto className="h-96 rounded-[28px]" />;

  return (
    <div className="flex flex-col gap-7 lg:max-w-3xl">
      <Titulo>Etiquetas</Titulo>

      <section className="flex flex-col gap-3 rounded-[24px] bg-surface p-5 shadow-soft">
        <div className="flex items-start gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px] bg-accent-soft text-accent"><Plane size={20} /></span>
          <div className="flex flex-1 flex-col gap-0.5">
            <b>{data.activa ? <>Etiqueta activa: <span className="text-accent">#{data.activa}</span></> : "¿Te vas de viaje o arrancás una mudanza?"}</b>
            <span className="text-[13px] text-muted">
              {data.activa
                ? "Todo lo que cargues (acá o por Telegram) la lleva sola, sea de la categoría que sea. Apagala cuando termine."
                : "Activá una etiqueta y todo lo que cargues la lleva solo. Al final ves cuánto te costó todo junto."}
            </span>
          </div>
        </div>
        {data.activa ? (
          <Boton variante="linea" onClick={() => activar(null)}><Power size={16} /> Apagar #{data.activa}</Boton>
        ) : (
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (limpiarEtiqueta(nueva)) activar(nueva); }}>
            <input className={inputCls} value={nueva} onChange={(e) => setNueva(e.target.value)} placeholder="#vacaciones2027" aria-label="Nombre de la etiqueta" />
            <Boton variante="acento" type="submit" disabled={!limpiarEtiqueta(nueva)}>Activar</Boton>
          </form>
        )}
      </section>

      {data.etiquetas.length ? (
        <Seccion titulo="Tus etiquetas">
          <div className="grid gap-3 sm:grid-cols-2">{data.etiquetas.map((e) => <Tarjeta key={e.id} e={e} />)}</div>
        </Seccion>
      ) : (
        <Vacio titulo="Todavía no usaste etiquetas">
          Escribí «#algo» cuando cargás un gasto (por ejemplo «cena 45k #salta»), o agregalas desde el detalle de cualquier movimiento.
        </Vacio>
      )}
    </div>
  );
}
