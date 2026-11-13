"use client";

import { Suspense, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import Link from "next/link";
import { CheckSquare, Download, Hash, Shapes, FileText, ShieldCheck, Plus, Search, Tags, X } from "lucide-react";
import { ExportarPanel } from "@/components/Exportar";
import { CategoriaPicker } from "@/components/Selectores";
import { Sheet } from "@/components/Sheet";
import { api, ApiError } from "@/lib/api";
import { vibrar } from "@/lib/hooks";
import { MovimientoFila } from "@/components/MovimientoFila";
import { useApp } from "@/components/Shell";
import { Boton, Chip, Esqueleto, Lista, Titulo, Vacio, cx } from "@/components/ui";
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
  const { abrirCaptura, aviso, refrescar } = useApp();
  const [elegidos, setElegidos] = useState<Set<string> | null>(null);
  const [recat, setRecat] = useState(false);
  const [exportar, setExportar] = useState(false);
  const eligiendo = elegidos !== null;
  const alternar = (m: Movimiento) => {
    const id = m.id;
    const otro = data?.find((x) => elegidos?.has(x.id));
    if (otro && otro.tipo !== m.tipo && !elegidos?.has(id)) {
      aviso("Elegí solo gastos o solo ingresos");
      return;
    }
    vibrar(8);
    setElegidos((prev) => {
      const s = new Set(prev ?? []);
      if (s.has(id)) s.delete(id);
      else s.add(id);
      return s;
    });
  };
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
          <div className="hidden gap-2 lg:flex">
            <Boton variante={eligiendo ? "primario" : "linea"} onClick={() => setElegidos(eligiendo ? null : new Set())}><CheckSquare size={17} /> Elegir varios</Boton>
            <Boton variante="linea" onClick={() => setExportar(true)}><Download size={17} /> Exportar</Boton>
            <Boton variante="acento" onClick={abrirCaptura}><Plus size={18} /> Cargar</Boton>
          </div>
        }
      >
        Movimientos
      </Titulo>
      <div className="no-scrollbar -mx-5 -mt-1 flex gap-2 overflow-x-auto px-5 lg:hidden">
        {[
          { label: "Elegir varios", Icon: CheckSquare, onClick: () => setElegidos(eligiendo ? null : new Set()), activo: eligiendo },
          { label: "Exportar", Icon: Download, onClick: () => setExportar(true) },
          { label: "Boletas", Icon: FileText, href: "/comprobantes" },
          { label: "Garantías", Icon: ShieldCheck, href: "/garantias" },
          { label: "Etiquetas", Icon: Hash, href: "/etiquetas" },
          { label: "Categorías", Icon: Shapes, href: "/categorias" },
        ].map(({ label, Icon, onClick, href, activo }) => {
          const cls = cx("press flex min-h-10 shrink-0 items-center gap-1.5 rounded-full border px-3.5 text-[13px] font-bold",
            activo ? "border-ink bg-ink text-ground" : "border-line-strong bg-surface");
          return href ? (
            <Link key={label} href={href} className={cls}><Icon size={15} /> {label}</Link>
          ) : (
            <button key={label} onClick={onClick} aria-pressed={activo} className={cls}><Icon size={15} /> {label}</button>
          );
        })}
      </div>

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
                <MovimientoFila key={m.id} mov={m} eligiendo={eligiendo} elegido={!!elegidos?.has(m.id)}
                  onElegir={m.tipo === "transferencia" ? undefined : () => alternar(m)} />
              ))}
            </Lista>
          </section>
        ))}
      </div>

      {eligiendo && createPortal(
        <div className="anim-aparecer fixed inset-x-0 bottom-[88px] z-40 flex justify-center px-4 lg:bottom-8 lg:pl-64">
          <div className="flex w-full max-w-md items-center gap-2 rounded-[22px] bg-ink p-2 pl-4 text-ground shadow-soft">
            <span className="min-w-0 flex-1 truncate text-sm font-bold">
              {elegidos.size === 0 ? "Tocá los que quieras cambiar" : `${elegidos.size} ${elegidos.size === 1 ? "elegido" : "elegidos"}`}
            </span>
            {data && elegidos.size > 0 && elegidos.size < data.filter((m) => m.tipo === data.find((x) => elegidos.has(x.id))?.tipo).length && (
              <button onClick={() => { const t = data.find((x) => elegidos.has(x.id))?.tipo; setElegidos(new Set(data.filter((m) => m.tipo === t).map((m) => m.id))); }}
                className="press min-h-10 rounded-xl px-2.5 text-sm font-bold opacity-80">Todos</button>
            )}
            <button disabled={!elegidos.size} onClick={() => setRecat(true)}
              className="press flex min-h-10 items-center gap-1.5 rounded-xl bg-accent px-3 text-sm font-bold text-accent-ink disabled:opacity-40">
              <Tags size={16} /> Categoría
            </button>
            <button aria-label="Cancelar" onClick={() => setElegidos(null)} className="press flex h-10 w-10 items-center justify-center rounded-xl bg-ground/15">
              <X size={18} />
            </button>
          </div>
        </div>,
        document.body
      )}

      <Sheet abierto={recat} onCerrar={() => setRecat(false)} titulo={`Cambiar categoría de ${elegidos?.size ?? 0}`}>
        <p className="-mt-2 text-sm text-muted">Elegí la nueva categoría y listo.</p>
        <CategoriaPicker
          valor={null}
          tipo={data?.find((m) => elegidos?.has(m.id))?.tipo === "ingreso" ? "ingreso" : "gasto"}
          onCambio={async (cat) => {
            try {
              const r = await api.post<{ actualizados: number }>("/movimientos/lote/categoria", { ids: [...(elegidos ?? [])], categoria_id: cat });
              vibrar();
              aviso(r.actualizados === 1 ? "1 movimiento recategorizado" : `${r.actualizados} movimientos recategorizados`);
              setRecat(false);
              setElegidos(null);
              refrescar();
            } catch (e) {
              aviso(e instanceof ApiError ? e.message : "No pude conectar con el servidor");
            }
          }}
        />
      </Sheet>

      <Sheet abierto={exportar} onCerrar={() => setExportar(false)} titulo="Exportar">
        <ExportarPanel />
      </Sheet>

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
