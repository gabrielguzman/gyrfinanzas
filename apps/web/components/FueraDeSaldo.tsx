"use client";

import useSWR from "swr";
import type { Cuenta, MedioPago } from "@/lib/api";
import { fechaCorta } from "@/lib/format";
import { cx } from "./ui";

/** La cuenta de un medio de pago (o de una cuenta) y la fecha en que la cargaste. */
export function useCuentaDe(medioId: string | null, cuentaId?: string | null) {
  const { data: medios } = useSWR<MedioPago[]>("/medios-pago");
  const { data: cuentas } = useSWR<Cuenta[]>("/cuentas");
  const id = cuentaId ?? medios?.find((m) => m.id === medioId)?.cuenta_id;
  return cuentas?.find((c) => c.id === id) ?? null;
}

/** ¿El movimiento es anterior a cuando cargaste la cuenta (y su saldo)? */
export function anteriorALaCuenta(fecha: string, cuenta: Cuenta | null): boolean {
  return !!cuenta?.creado && fecha < cuenta.creado.slice(0, 10);
}

/** «Ya estaba descontado del saldo»: cuenta en gastos y reportes, pero no mueve el saldo. */
export function FueraDeSaldo({
  activo,
  onCambio,
  cuenta,
  ingreso,
  sugerido,
}: {
  activo: boolean;
  onCambio: (v: boolean) => void;
  cuenta: Cuenta | null;
  ingreso?: boolean;
  sugerido?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={activo}
      onClick={() => onCambio(!activo)}
      className={cx("press flex w-full items-center gap-3 rounded-2xl border p-3.5 text-left", activo ? "border-accent bg-accent-soft" : "border-line-strong bg-surface")}
    >
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-sm font-bold">{ingreso ? "Ya estaba sumado al saldo" : "Ya estaba descontado del saldo"}</span>
        <span className="text-[12px] leading-snug text-muted">
          {activo
            ? `No cambia el saldo${cuenta ? ` de ${cuenta.nombre}` : ""}. Igual cuenta en tus ${ingreso ? "ingresos" : "gastos"} del mes y en las categorías.`
            : sugerido && cuenta?.creado
              ? `Es anterior a cuando cargaste ${cuenta.nombre} (${fechaCorta(cuenta.creado.slice(0, 10))}): seguro el saldo que pusiste ya lo incluye.`
              : "Prendelo si el saldo que cargaste en la cuenta ya lo tenía en cuenta."}
        </span>
      </span>
      <span className={cx("relative h-7 w-12 shrink-0 rounded-full transition-colors", activo ? "bg-accent" : "bg-line-strong")} aria-hidden>
        <span className={cx("absolute top-1 left-1 h-5 w-5 rounded-full bg-white shadow transition-transform", activo && "translate-x-5")} />
      </span>
    </button>
  );
}
