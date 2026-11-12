"use client";

import { useState } from "react";
import useSWR from "swr";
import { Hash, X } from "lucide-react";
import type { EtiquetaResumen, Etiquetas } from "@/lib/api";
import { fechaCorta } from "@/lib/format";
import { cx } from "./ui";

export function rango(e: EtiquetaResumen) {
  if (!e.desde) return "Sin gastos todavía";
  return e.desde === e.hasta ? fechaCorta(e.desde) : `${fechaCorta(e.desde)} al ${fechaCorta(e.hasta)}`;
}

export const limpiarEtiqueta = (t: string) =>
  t.trim().replace(/^#+/, "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9_-]/g, "").slice(0, 40);

/** Chips de etiquetas con «agregar» y sugerencias de las que ya usaste. */
export function EtiquetasEditor({ valor, onCambio }: { valor: string[]; onCambio: (v: string[]) => void }) {
  const { data } = useSWR<Etiquetas>("/etiquetas");
  const [texto, setTexto] = useState("");
  const agregar = (t: string) => {
    const n = limpiarEtiqueta(t);
    if (n && !valor.includes(n)) onCambio([...valor, n]);
    setTexto("");
  };
  const q = limpiarEtiqueta(texto);
  const sugeridas = (data?.etiquetas ?? []).map((e) => e.nombre).filter((n) => !valor.includes(n) && (!q || n.includes(q))).slice(0, 5);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-1.5">
        {valor.map((t) => (
          <span key={t} data-cat="pink" className="flex min-h-9 items-center gap-1 rounded-full bg-[var(--cat-bg)] py-1 pr-1 pl-3 text-[13px] font-bold text-[var(--cat-fg)]">
            #{t}
            <button aria-label={`Sacar #${t}`} onClick={() => onCambio(valor.filter((x) => x !== t))} className="press flex h-7 w-7 items-center justify-center rounded-full hover:bg-black/10">
              <X size={14} />
            </button>
          </span>
        ))}
        <label className="flex min-h-9 min-w-[150px] flex-1 items-center gap-1 rounded-full border border-dashed border-line-strong px-3">
          <Hash size={14} className="text-faint" />
          <input
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === "," || e.key === " ") {
                e.preventDefault();
                agregar(texto);
              } else if (e.key === "Backspace" && !texto && valor.length) onCambio(valor.slice(0, -1));
            }}
            onBlur={() => texto && agregar(texto)}
            placeholder={valor.length ? "otra" : "vacaciones, mudanza…"}
            aria-label="Agregar etiqueta"
            className="w-full bg-transparent text-[13px] font-semibold outline-none placeholder:text-faint"
          />
        </label>
      </div>
      {sugeridas.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {sugeridas.map((n) => (
            <button key={n} onMouseDown={(e) => e.preventDefault()} onClick={() => agregar(n)}
              className={cx("press min-h-8 rounded-full bg-surface-2 px-2.5 text-[12px] font-bold text-muted")}>
              + #{n}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
