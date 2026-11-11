"use client";

import { Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import Link from "next/link";
import { FileText, ShieldCheck, Plus, Search, X } from "lucide-react";
import { MovimientoFila } from "@/components/MovimientoFila";
import { useApp } from "@/components/Shell";
import { Boton, Chip, Esqueleto, Lista, Titulo, Vacio } from "@/components/ui";
import type { Categoria, Movimiento } from "@/lib/api";
import { etiquetaDia, monto } from "@/lib/format";

const FILTROS = [
  { id: "todos", label: "Todos", qs: "" },
  { id: "pendientes", label: "Por confirmar", qs: "estado=pendiente" },
  { id: "sin_comprobante", label: "Sin comprobante", qs: "sin_comprobante=true" },
  { id: "gastos", label: "Gastos", qs: "tipo=gasto" },
  { id: "ingresos", label: "Ingresos", qs: "tipo=ingreso" },
  { id: "transferencias", label: "Transferencias", qs: "tipo=transferencia" },
];

function Lista_() {
  const { abrirCaptura } = useApp();
  const params = useSearchParams();
  const inicial = params.get("filtro") ?? "todos";
  const [filtro, setFiltro] = useState(FILTROS.some((f) => f.id === inicial) ? inicial : "todos");
  const [q, setQ] = useState(params.get("q") ?? "");
  const [categoria, setCategoria] = useState(params.get("categoria"));
  const { data: cats } = useSWR<Categoria[]>(categoria ? "/categorias" : null);
  const nombreCat = cats?.find((c) => c.id === categoria)?.nombre;

  const qs = [
    FILTROS.find((f) => f.id === filtro)?.qs,
    q.trim() && `q=${encodeURIComponent(q.trim())}`,
    categoria && `categoria_id=${categoria}`,
    "limit=300",
  ]
    .filter(Boolean)
    .join("&");
  const { data, isLoading } = useSWR<Movimiento[]>(`/movimientos?${qs}`);

  const grupos = useMemo(() => {
    const g: { dia: string; items: Movimiento[]; gasto: number }[] = [];
    data?.forEach((m) => {
      let ult = g[g.length - 1];
      if (!ult || ult.dia !== m.fecha) {
        ult = { dia: m.fecha, items: [], gasto: 0 };
        g.push(ult);
      }
      ult.items.push(m);
      if (m.tipo === "gasto" && m.estado === "confirmado" && m.moneda === "ARS") ult.gasto += Number(m.monto);
    });
    return g;
  }, [data]);

  return (
    <div className="flex flex-col gap-5">
      <Titulo
        extra={
          <>
            <Link href="/comprobantes" aria-label="Comprobantes" className="press flex min-h-11 items-center gap-1.5 rounded-2xl border border-line-strong bg-surface px-3.5 text-sm font-bold lg:hidden">
              <FileText size={16} /> Boletas
            </Link>
            <Link href="/garantias" aria-label="Garantías" className="press flex min-h-11 items-center gap-1.5 rounded-2xl border border-line-strong bg-surface px-3.5 text-sm font-bold lg:hidden">
              <ShieldCheck size={16} /> Garantías
            </Link>
            <div className="hidden lg:block"><Boton variante="acento" onClick={abrirCaptura}><Plus size={18} /> Cargar</Boton></div>
          </>
        }
      >
        Movimientos
      </Titulo>

      <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
        <label className="flex min-h-12 flex-1 items-center gap-2.5 rounded-2xl bg-surface px-4 shadow-soft lg:max-w-sm">
          <Search size={18} className="text-faint" aria-hidden />
          <span className="sr-only">Buscar</span>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar: nafta, súper…"
            className="flex-1 bg-transparent text-[15px] outline-none placeholder:text-faint"
          />
        </label>
        <div className="no-scrollbar -mx-5 flex gap-1.5 overflow-x-auto px-5 pb-1 lg:mx-0 lg:flex-wrap lg:px-0">
          {FILTROS.map((f) => (
            <Chip key={f.id} activo={filtro === f.id} onClick={() => setFiltro(f.id)}>
              {f.label}
            </Chip>
          ))}
        </div>
      </div>

      {categoria && (
        <div className="flex w-fit items-center gap-2 rounded-full bg-accent-soft py-1.5 pr-1.5 pl-3.5 text-sm font-bold">
          Solo {nombreCat ?? "una categoría"}
          <button onClick={() => setCategoria(null)} aria-label="Quitar filtro de categoría" className="press flex h-7 w-7 items-center justify-center rounded-full bg-surface">
            <X size={14} />
          </button>
        </div>
      )}

      {isLoading && !data && <Esqueleto className="h-80 rounded-[22px]" />}

      <div className="flex flex-col gap-6 lg:max-w-3xl">
        {grupos.map((g) => (
          <section key={g.dia} className="flex flex-col gap-2">
            <div className="flex items-baseline justify-between px-1">
              <h2 className="text-sm font-bold">{etiquetaDia(g.dia)}</h2>
              {g.gasto > 0 && <span className="num text-[13px] font-semibold text-muted">{monto(g.gasto)} gastados</span>}
            </div>
            <Lista>
              {g.items.map((m) => (
                <MovimientoFila key={m.id} mov={m} />
              ))}
            </Lista>
          </section>
        ))}
      </div>

      {!isLoading && data?.length === 0 && (
        filtro === "todos" && !q.trim() ? (
          <Vacio titulo="Todavía no cargaste nada" accion={<Boton variante="acento" onClick={abrirCaptura}><Plus size={18} /> Cargar el primero</Boton>}>
            Escribilo como te salga, por ejemplo «café 2500 mp».
          </Vacio>
        ) : (
          <Vacio titulo="Nada con este filtro">Probá con otro filtro o buscá otra palabra.</Vacio>
        )
      )}
    </div>
  );
}

export default function MovimientosPage() {
  return (
    <Suspense>
      <Lista_ />
    </Suspense>
  );
}
