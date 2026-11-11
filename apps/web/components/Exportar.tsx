"use client";

import { useState } from "react";
import { Download, FileSpreadsheet, FileText } from "lucide-react";
import { apiBase } from "@/lib/api";
import { MESES, hoyISO } from "@/lib/format";
import { Chip, cx } from "./ui";

type Periodo = "todo" | "mes" | "mes_pasado" | "anio";

function rango(p: Periodo): { desde?: string; hasta?: string } {
  const h = new Date();
  const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  if (p === "mes") return { desde: iso(new Date(h.getFullYear(), h.getMonth(), 1)), hasta: hoyISO() };
  if (p === "mes_pasado") return { desde: iso(new Date(h.getFullYear(), h.getMonth() - 1, 1)), hasta: iso(new Date(h.getFullYear(), h.getMonth(), 0)) };
  if (p === "anio") return { desde: `${h.getFullYear()}-01-01`, hasta: hoyISO() };
  return {};
}

/** Elegís formato y período, y se descarga. */
export function ExportarPanel() {
  const [formato, setFormato] = useState<"xlsx" | "csv">("xlsx");
  const [periodo, setPeriodo] = useState<Periodo>("todo");
  const h = new Date();
  const pasado = new Date(h.getFullYear(), h.getMonth() - 1, 1);
  const r = rango(periodo);
  const qs = new URLSearchParams({ formato, ...(r.desde ? { desde: r.desde } : {}), ...(r.hasta ? { hasta: r.hasta } : {}) });
  const opciones: { id: "xlsx" | "csv"; titulo: string; detalle: string; Icon: typeof FileText }[] = [
    { id: "xlsx", titulo: "Excel", detalle: "Movimientos, resumen por mes y categoría, cuentas, cuotas, deudas y fijos", Icon: FileSpreadsheet },
    { id: "csv", titulo: "CSV", detalle: "Solo movimientos, para Excel, Sheets u otra app", Icon: FileText },
  ];
  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-2 sm:grid-cols-2">
        {opciones.map(({ id, titulo, detalle, Icon }) => (
          <button key={id} onClick={() => setFormato(id)} aria-pressed={formato === id}
            className={cx("press flex items-start gap-3 rounded-2xl border-2 bg-surface p-3.5 text-left", formato === id ? "border-ink" : "border-transparent shadow-soft")}>
            <Icon size={22} className={cx("mt-0.5 shrink-0", id === "xlsx" ? "text-ok" : "text-muted")} />
            <span className="flex flex-col gap-0.5"><b>{titulo}</b><span className="text-[13px] text-muted">{detalle}</span></span>
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-1.5">
        <Chip activo={periodo === "todo"} onClick={() => setPeriodo("todo")}>Todo</Chip>
        <Chip activo={periodo === "mes"} onClick={() => setPeriodo("mes")}>Este mes</Chip>
        <Chip activo={periodo === "mes_pasado"} onClick={() => setPeriodo("mes_pasado")}>{MESES[pasado.getMonth()][0].toUpperCase() + MESES[pasado.getMonth()].slice(1)}</Chip>
        <Chip activo={periodo === "anio"} onClick={() => setPeriodo("anio")}>{h.getFullYear()}</Chip>
      </div>
      <a href={`${apiBase()}/exportar?${qs}`} download
        className="press inline-flex min-h-12 items-center justify-center gap-2 rounded-2xl bg-ink px-4 text-sm font-bold text-ground">
        <Download size={18} /> Descargar {formato === "xlsx" ? "Excel" : "CSV"}
      </a>
    </div>
  );
}
