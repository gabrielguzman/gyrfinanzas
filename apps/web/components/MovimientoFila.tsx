"use client";

import { ArrowLeftRight, Paperclip } from "lucide-react";
import type { Movimiento } from "@/lib/api";
import { monto } from "@/lib/format";
import { useApp } from "./Shell";
import { IconoCat, cx } from "./ui";

export function MovimientoFila({ mov }: { mov: Movimiento }) {
  const { abrirMovimiento } = useApp();
  const ingreso = mov.tipo === "ingreso";
  const transfer = mov.tipo === "transferencia";
  const sub = transfer
    ? `${mov.cuenta} a ${mov.cuenta_destino}`
    : [mov.categoria ?? "Sin categoría", mov.medio_pago].filter(Boolean).join(", ");

  return (
    <button
      onClick={() => abrirMovimiento(mov.id)}
      className="press flex min-h-[64px] w-full items-center gap-3 bg-surface px-4 py-2.5 text-left hover:bg-surface-2"
    >
      {transfer ? (
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[14px] bg-surface-2 text-muted" aria-hidden>
          <ArrowLeftRight size={19} />
        </span>
      ) : (
        <IconoCat icono={mov.categoria_icono} color={mov.categoria_color} />
      )}
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="flex items-center gap-1.5 text-[15px] font-bold">
          <span className="truncate">{mov.descripcion}</span>
          {mov.tiene_comprobante && <Paperclip size={14} className="shrink-0 text-faint" aria-label="Con comprobante" />}
          {mov.estado === "pendiente" && (
            <span className="shrink-0 rounded-md bg-warn-soft px-1.5 py-0.5 text-[11px] font-bold text-warn-ink">por confirmar</span>
          )}
        </span>
        <span className="truncate text-[13px] text-muted">{sub}</span>
      </span>
      <span className={cx("num shrink-0 text-[15px] font-extrabold", ingreso && "text-ok", transfer && "text-muted")}>
        {monto(mov.monto, mov.moneda, ingreso ? "+" : transfer ? undefined : "-")}
      </span>
    </button>
  );
}
