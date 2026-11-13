"use client";

import { useState } from "react";
import useSWR from "swr";
import { Plus, Sparkles } from "lucide-react";
import { CategoriaSheet, type CategoriaAbierta } from "@/components/CategoriaSheet";
import { useApp } from "@/components/Shell";
import { Boton, Chip, Esqueleto, IconoCat, Seccion, Titulo, cx } from "@/components/ui";
import { api, type Categoria } from "@/lib/api";

type ConUso = Categoria & { cantidad: number };
interface Sugerida { nombre: string; tipo: "gasto" | "ingreso"; palabras: string; icono: string; color: string }

export default function CategoriasPage() {
  const { data, mutate } = useSWR<ConUso[]>("/categorias/uso");
  const { data: sugeridas, mutate: mutarSug } = useSWR<Sugerida[]>("/categorias/sugeridas");
  const { aviso, refrescar } = useApp();
  const [tipo, setTipo] = useState<"gasto" | "ingreso">("gasto");
  const [abierta, setAbierta] = useState<CategoriaAbierta>(null);
  const [agregando, setAgregando] = useState(false);

  const lista = (data ?? []).filter((c) => c.tipo === tipo).sort((a, b) => b.cantidad - a.cantidad || a.nombre.localeCompare(b.nombre));
  const sug = (sugeridas ?? []).filter((s) => s.tipo === tipo);

  async function agregar(nombres: string[]) {
    setAgregando(true);
    try {
      await api.post("/categorias/sugeridas", { nombres });
      aviso(nombres.length === 1 ? `Agregaste ${nombres[0]}` : `Agregaste ${nombres.length} categorías`);
      mutate();
      mutarSug();
      refrescar();
    } finally {
      setAgregando(false);
    }
  }

  return (
    <div className="flex flex-col gap-7 lg:max-w-3xl">
      <Titulo extra={<Boton variante="linea" onClick={() => setAbierta({ nueva: true, tipo })}><Plus size={18} /> Nueva</Boton>}>Categorías</Titulo>

      <div className="flex gap-1.5">
        <Chip activo={tipo === "gasto"} onClick={() => setTipo("gasto")}>Gastos</Chip>
        <Chip activo={tipo === "ingreso"} onClick={() => setTipo("ingreso")}>Ingresos</Chip>
      </div>

      {sug.length > 0 && (
        <section className="flex flex-col gap-3 rounded-[24px] border-2 border-dashed border-accent/40 bg-accent-soft/50 p-5">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[14px] bg-accent text-accent-ink"><Sparkles size={19} /></span>
            <div className="flex flex-1 flex-col gap-0.5">
              <b>Clásicas que todavía no tenés</b>
              <span className="text-sm text-muted">Vienen con ícono, color y las palabras que las reconocen al cargar. Tocá las que uses.</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {sug.map((s) => (
              <button key={s.nombre} disabled={agregando} onClick={() => agregar([s.nombre])}
                className="press flex min-h-10 items-center gap-2 rounded-full border border-line-strong bg-surface py-1 pr-3.5 pl-1.5 text-[13px] font-bold disabled:opacity-50">
                <IconoCat icono={s.icono} color={s.color} size={28} /> {s.nombre} <Plus size={14} className="text-accent" />
              </button>
            ))}
          </div>
          {sug.length > 1 && (
            <Boton variante="primario" disabled={agregando} onClick={() => agregar(sug.map((s) => s.nombre))}>Agregar las {sug.length}</Boton>
          )}
        </section>
      )}

      <Seccion titulo={tipo === "gasto" ? "Tus categorías de gastos" : "Tus categorías de ingresos"}>
        {!data ? <Esqueleto className="h-64 rounded-[22px]" /> : (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {lista.map((c) => (
              <button key={c.id} onClick={() => setAbierta({ categoria: c })}
                className="press flex items-center gap-3 rounded-[18px] bg-surface p-3 text-left shadow-soft hover:bg-surface-2">
                <IconoCat icono={c.icono} color={c.color} size={40} />
                <span className="flex min-w-0 flex-col">
                  <span className="truncate text-[14px] font-bold">{c.nombre}</span>
                  <span className={cx("text-[12px]", c.cantidad ? "text-muted" : "text-faint")}>{c.cantidad ? `${c.cantidad} ${c.cantidad === 1 ? "movimiento" : "movimientos"}` : "Sin usar"}</span>
                </span>
              </button>
            ))}
            <button onClick={() => setAbierta({ nueva: true, tipo })}
              className="press flex items-center gap-3 rounded-[18px] border-2 border-dashed border-line-strong p-3 text-left text-muted">
              <span className="flex h-10 w-10 items-center justify-center rounded-[14px] bg-surface-2"><Plus size={20} /></span>
              <span className="text-[14px] font-bold">Nueva</span>
            </button>
          </div>
        )}
      </Seccion>

      <CategoriaSheet abierta={abierta} onCerrar={() => { setAbierta(null); mutate(); mutarSug(); }} />
    </div>
  );
}
