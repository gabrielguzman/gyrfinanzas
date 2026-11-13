"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { Trash2, X } from "lucide-react";
import { api, ApiError, type Categoria } from "@/lib/api";
import { COLORES, ICONOS_CATEGORIA } from "@/lib/categorias";
import { Sheet } from "./Sheet";
import { useApp } from "./Shell";
import { Boton, Chip, IconoCat, Mensaje, cx, inputCls } from "./ui";

function Bloque({ label, ayuda, children }: { label: string; ayuda?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[13px] font-semibold text-muted">{label}</span>
      {children}
      {ayuda && <span className="text-xs text-faint">{ayuda}</span>}
    </div>
  );
}

type Abierta = { nueva: true; tipo: "gasto" | "ingreso"; nombre?: string } | { categoria: Categoria & { cantidad?: number } } | null;

/** Alta y edición de una categoría: nombre, ícono, color y palabras que la eligen sola. */
export function CategoriaSheet({ abierta, onCerrar, onCreada }: { abierta: Abierta; onCerrar: () => void; onCreada?: (c: Categoria) => void }) {
  const { aviso, refrescar } = useApp();
  const c = abierta && "categoria" in abierta ? abierta.categoria : null;
  const tipo = c?.tipo ?? (abierta && "tipo" in abierta ? abierta.tipo : "gasto");
  const { data: todas } = useSWR<Categoria[]>(abierta ? "/categorias" : null);
  const [nombre, setNombre] = useState("");
  const [icono, setIcono] = useState("otros");
  const [color, setColor] = useState<string>("slate");
  const [palabras, setPalabras] = useState<string[]>([]);
  const [palabra, setPalabra] = useState("");
  const [borrando, setBorrando] = useState(false);
  const [moverA, setMoverA] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    if (!abierta) return;
    setNombre(c?.nombre ?? (abierta && "nombre" in abierta ? abierta.nombre ?? "" : ""));
    setIcono(c?.icono || "otros");
    setColor(c?.color || "slate");
    setPalabras((c?.palabras ?? "").split(",").map((p) => p.trim()).filter(Boolean));
    setPalabra("");
    setBorrando(false);
    setMoverA(null);
    setError(null);
  }, [abierta, c]);

  const agregarPalabra = () => {
    const p = palabra.trim().toLowerCase();
    if (p && !palabras.includes(p)) setPalabras([...palabras, p]);
    setPalabra("");
  };

  async function guardar() {
    setOcupado(true);
    setError(null);
    const datos = { nombre: nombre.trim(), icono, color, palabras: [...palabras, ...(palabra.trim() ? [palabra.trim().toLowerCase()] : [])].join(",") };
    try {
      if (c) {
        await api.patch(`/categorias/${c.id}`, datos);
        aviso("Categoría guardada");
      } else {
        const nueva = await api.post<Categoria>("/categorias", { ...datos, tipo });
        aviso(`Creaste ${nueva.nombre}`);
        onCreada?.(nueva);
      }
      refrescar();
      onCerrar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No pude conectar con el servidor");
    } finally {
      setOcupado(false);
    }
  }

  async function borrar() {
    if (!c) return;
    setOcupado(true);
    try {
      await api.del(`/categorias/${c.id}${moverA ? `?mover_a=${moverA}` : ""}`);
      const destino = todas?.find((x) => x.id === moverA)?.nombre;
      aviso(destino ? `Borrada: sus movimientos pasaron a ${destino}` : `Borraste ${c.nombre}`);
      refrescar();
      onCerrar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No pude conectar con el servidor");
    } finally {
      setOcupado(false);
    }
  }

  const otras = (todas ?? []).filter((x) => x.tipo === tipo && x.id !== c?.id);

  return (
    <Sheet abierto={!!abierta} onCerrar={onCerrar} titulo={c ? c.nombre : tipo === "ingreso" ? "Nueva categoría de ingreso" : "Nueva categoría"}>
      <div className="flex items-center gap-3">
        <IconoCat icono={icono} color={color} size={56} />
        <input className={inputCls} value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Kiosco, Mascotas, Gimnasio…" aria-label="Nombre" autoFocus={!c} />
      </div>

      <Bloque label="Ícono">
        <div className="grid grid-cols-8 gap-1.5">
          {ICONOS_CATEGORIA.map((k) => (
            <button key={k} type="button" aria-label={k} aria-pressed={icono === k} onClick={() => setIcono(k)}
              className={cx("press flex aspect-square items-center justify-center rounded-xl border-2", icono === k ? "border-ink" : "border-transparent")}>
              <IconoCat icono={k} color={color} size={32} />
            </button>
          ))}
        </div>
      </Bloque>

      <Bloque label="Color">
        <div className="flex flex-wrap gap-2">
          {COLORES.map((col) => (
            <button key={col} type="button" aria-label={col} aria-pressed={color === col} onClick={() => setColor(col)}
              data-cat={col} className={cx("press h-9 w-9 rounded-full border-[3px] bg-[var(--cat-fg)]", color === col ? "border-ink" : "border-transparent")} />
          ))}
        </div>
      </Bloque>

      <Bloque label="Se elige sola si escribís…" ayuda="Palabras que, si aparecen al cargar, eligen esta categoría. Para casos puntuales también están las reglas en Ajustes.">
        <div className="flex flex-wrap items-center gap-1.5">
          {palabras.map((p) => (
            <span key={p} className="flex min-h-8 items-center gap-1 rounded-full bg-surface-2 py-0.5 pr-1 pl-3 text-[13px] font-bold">
              {p}
              <button type="button" aria-label={`Sacar ${p}`} onClick={() => setPalabras(palabras.filter((x) => x !== p))} className="press flex h-6 w-6 items-center justify-center rounded-full hover:bg-line">
                <X size={13} />
              </button>
            </span>
          ))}
          <input value={palabra} onChange={(e) => setPalabra(e.target.value)} placeholder={palabras.length ? "otra" : "ej. alfajor"}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); agregarPalabra(); } }}
            onBlur={agregarPalabra}
            className="min-h-8 min-w-[110px] flex-1 rounded-full border border-dashed border-line-strong bg-transparent px-3 text-[13px] font-semibold outline-none" />
        </div>
      </Bloque>

      {error && <Mensaje tono="error">{error}</Mensaje>}
      <Boton variante="acento" disabled={!nombre.trim() || ocupado} onClick={guardar}>{c ? "Guardar" : "Crear categoría"}</Boton>

      {c && !borrando && (
        <Boton variante="peligro" onClick={() => setBorrando(true)}><Trash2 size={16} /> Borrar categoría</Boton>
      )}
      {c && borrando && (
        <div className="flex flex-col gap-3 rounded-2xl bg-danger-soft p-4">
          <p className="text-sm font-semibold">
            {c.cantidad ? `Tiene ${c.cantidad} ${c.cantidad === 1 ? "movimiento" : "movimientos"}. ¿A qué categoría los paso?` : "¿Seguro? No tiene movimientos."}
          </p>
          {!!c.cantidad && (
            <div className="flex flex-wrap gap-1.5">
              <Chip activo={moverA === null} onClick={() => setMoverA(null)}>Dejarlos sin categoría</Chip>
              {otras.map((o) => <Chip key={o.id} activo={moverA === o.id} onClick={() => setMoverA(o.id)}>{o.nombre}</Chip>)}
            </div>
          )}
          <div className="grid grid-cols-2 gap-2">
            <Boton variante="linea" onClick={() => setBorrando(false)}>Cancelar</Boton>
            <Boton variante="peligro" disabled={ocupado} onClick={borrar}>{moverA ? "Pasar y borrar" : "Borrar"}</Boton>
          </div>
        </div>
      )}
    </Sheet>
  );
}

export type { Abierta as CategoriaAbierta };
