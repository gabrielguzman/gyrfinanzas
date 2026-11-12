"use client";

import { useRef } from "react";
import { ArrowLeftRight, Check, Paperclip } from "lucide-react";
import type { Movimiento } from "@/lib/api";
import { monto } from "@/lib/format";
import { useApp } from "./Shell";
import { IconoCat, cx } from "./ui";

export function MovimientoFila({
  mov,
  eligiendo,
  elegido,
  onElegir,
}: {
  mov: Movimiento;
  /** Modo selección: tocar elige en vez de abrir. */
  eligiendo?: boolean;
  elegido?: boolean;
  /** Alternar selección (también se llama con un toque largo para entrar al modo). */
  onElegir?: () => void;
}) {
  const { abrirMovimiento } = useApp();
  const largo = useRef<number | undefined>(undefined);
  const disparado = useRef(false);
  const ingreso = mov.tipo === "ingreso";
  const transfer = mov.tipo === "transferencia";
  const sub = transfer
    ? `${mov.cuenta} a ${mov.cuenta_destino}`
    : [mov.categoria ?? "Sin categoría", mov.medio_pago].filter(Boolean).join(", ");

  return (
    <button
      onClick={() => {
        if (disparado.current) return void (disparado.current = false);
        if (eligiendo && onElegir) onElegir();
        else abrirMovimiento(mov.id);
      }}
      onPointerDown={() => {
        if (!onElegir || eligiendo) return;
        disparado.current = false;
        largo.current = window.setTimeout(() => { disparado.current = true; onElegir(); }, 480);
      }}
      onPointerUp={() => window.clearTimeout(largo.current)}
      onPointerLeave={() => window.clearTimeout(largo.current)}
      onPointerMove={(e) => { if (Math.abs(e.movementY) > 2) window.clearTimeout(largo.current); }}
      onContextMenu={(e) => onElegir && e.preventDefault()}
      aria-pressed={eligiendo ? !!elegido : undefined}
      className={cx("press flex min-h-[64px] w-full items-center gap-3 px-4 py-2.5 text-left select-none", elegido ? "bg-accent-soft" : "bg-surface hover:bg-surface-2")}
    >
      {eligiendo ? (
        <span className={cx("flex h-10 w-10 shrink-0 items-center justify-center rounded-full border-2", elegido ? "border-accent bg-accent text-accent-ink" : "border-line-strong")} aria-hidden>
          {elegido && <Check size={20} strokeWidth={3} />}
        </span>
      ) : transfer ? (
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
          {mov.fuera_de_saldo && (
            <span className="shrink-0 rounded-md bg-surface-2 px-1.5 py-0.5 text-[11px] font-bold text-muted" title="Ya estaba descontado del saldo: no lo mueve">fuera del saldo</span>
          )}
          {mov.estado === "pendiente" && (
            <span className="shrink-0 rounded-md bg-warn-soft px-1.5 py-0.5 text-[11px] font-bold text-warn-ink">por confirmar</span>
          )}
        </span>
        <span className="truncate text-[13px] text-muted">
          {sub}
          {mov.etiquetas?.length > 0 && <span data-cat="pink" className="font-bold text-[var(--cat-fg)]"> {mov.etiquetas.map((t) => `#${t}`).join(" ")}</span>}
        </span>
      </span>
      <span className={cx("num shrink-0 text-[15px] font-extrabold", ingreso && "text-ok", transfer && "text-muted")}>
        {monto(mov.monto, mov.moneda, ingreso ? "+" : transfer ? undefined : "-")}
      </span>
    </button>
  );
}
