"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
import { Pencil, Power, Trash2 } from "lucide-react";
import { CategoriasBarras } from "@/components/Graficos";
import { MovimientoFila } from "@/components/MovimientoFila";
import { useApp } from "@/components/Shell";
import { Boton, Esqueleto, Lista, Mensaje, Seccion, inputCls } from "@/components/ui";
import { api, ApiError, type EtiquetaResumen, type Movimiento } from "@/lib/api";
import { monto } from "@/lib/format";
import { rango } from "@/components/EtiquetasEditor";

export default function EtiquetaPage() {
  const { nombre } = useParams<{ nombre: string }>();
  const router = useRouter();
  const { aviso, refrescar } = useApp();
  const { data: e, mutate, error } = useSWR<EtiquetaResumen>(`/etiquetas/${nombre}`);
  const { data: movs } = useSWR<Movimiento[]>(`/movimientos?etiqueta=${nombre}&limit=500`);
  const [editando, setEditando] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  if (error) return <Mensaje tono="error">No encontré #{nombre}.</Mensaje>;
  if (!e) return <Esqueleto className="h-96 rounded-[28px]" />;
  const total = Number(e.total);

  return (
    <div className="flex flex-col gap-7 lg:max-w-3xl">
      <section data-cat="pink" className="flex flex-col gap-2 rounded-[28px] bg-[var(--cat-bg)] p-6">
        {editando === null ? (
          <h1 className="display text-[34px] leading-none font-bold text-[var(--cat-fg)]">#{e.nombre}</h1>
        ) : (
          <form className="flex gap-2" onSubmit={async (ev) => {
            ev.preventDefault();
            try {
              const r = await api.patch<EtiquetaResumen>(`/etiquetas/${e.id}`, { nombre: editando });
              setEditando(null);
              router.replace(`/etiquetas/${r.nombre}`);
            } catch (x) {
              setErr(x instanceof ApiError ? x.message : "No pude conectar");
            }
          }}>
            <input autoFocus className={inputCls} value={editando} onChange={(ev) => setEditando(ev.target.value)} />
            <Boton variante="primario" type="submit">Guardar</Boton>
          </form>
        )}
        <span className="text-sm font-semibold text-muted">{rango(e)} · {e.cantidad} {e.cantidad === 1 ? "gasto" : "gastos"}</span>
        <span className="display num mt-2 text-[44px] leading-none font-bold">{monto(Math.round(total))}</span>
        {Number(e.total_usd) > 0 && <span className="num font-bold text-muted">+ {monto(e.total_usd, "USD")}</span>}
        <div className="mt-3 flex flex-wrap gap-2">
          <Boton variante="linea" onClick={async () => { await api.put("/etiquetas/activa", { nombre: e.activa ? null : e.nombre }); mutate(); refrescar(); }}>
            <Power size={16} /> {e.activa ? "Apagar" : "Activar"}
          </Boton>
          <Boton variante="linea" onClick={() => setEditando(e.nombre)}><Pencil size={16} /> Renombrar</Boton>
          <Boton variante="peligro" onClick={async () => {
            await api.del(`/etiquetas/${e.id}`);
            aviso(`Saqué #${e.nombre} de ${e.cantidad} movimientos`);
            refrescar();
            router.replace("/etiquetas");
          }}><Trash2 size={16} /> Borrar</Boton>
        </div>
        {err && <Mensaje tono="error">{err}</Mensaje>}
      </section>

      {e.por_categoria.length > 0 && (
        <Seccion titulo="En qué se fue">
          <div className="rounded-[22px] bg-surface p-5 shadow-soft">
            <CategoriasBarras total={total} items={e.por_categoria.map((c) => ({ categoria_id: null, nombre: c.nombre, icono: c.icono, color: c.color, total: c.total, cantidad: 0 }))} />
          </div>
        </Seccion>
      )}

      <Seccion titulo="Movimientos">
        {movs ? (
          movs.length ? <Lista>{movs.map((m) => <MovimientoFila key={m.id} mov={m} />)}</Lista> : <p className="text-sm text-muted">Nada con esta etiqueta todavía.</p>
        ) : <Esqueleto className="h-40 rounded-[22px]" />}
      </Seccion>
    </div>
  );
}
