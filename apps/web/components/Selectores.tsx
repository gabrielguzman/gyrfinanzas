"use client";

import { useRef, useState } from "react";
import useSWR from "swr";
import { CalendarDays } from "lucide-react";
import type { Categoria, Cuenta, MedioPago, Moneda } from "@/lib/api";
import { hoyISO, sumarDias } from "@/lib/format";
import { Chip, IconoCat, cx } from "./ui";

export function MedioChips({ valor, onCambio, soloCredito }: { valor: string | null; onCambio: (id: string) => void; soloCredito?: boolean }) {
  const { data: todos } = useSWR<MedioPago[]>("/medios-pago");
  if (!todos) return <div className="esqueleto h-10 w-full" />;
  // En cuotas solo tiene sentido una tarjeta de crédito
  const medios = soloCredito ? todos.filter((m) => m.tipo === "credito" && !m.archivado) : todos;
  if (!todos.length) return <p className="text-sm text-muted">Primero creá tus cuentas y medios de pago en Cuentas.</p>;
  if (!medios.length)
    return (
      <p className="text-sm text-muted">
        Las cuotas van con tarjeta de crédito y no tenés ninguna cargada.{" "}
        <a href="/cuentas" className="font-bold text-accent">Cargá tu tarjeta en Cuentas</a>.
      </p>
    );
  return (
    <div className="flex flex-wrap gap-1.5">
      {medios.map((m) => (
        <Chip key={m.id} activo={valor === m.id} onClick={() => onCambio(m.id)}>
          {m.nombre}
        </Chip>
      ))}
    </div>
  );
}

/** Cuentas donde puede entrar plata (sin tarjetas de crédito), para ingresos. */
export function CuentaChips({ valor, onCambio, moneda }: { valor: string | null; onCambio: (id: string) => void; moneda?: Moneda }) {
  const { data } = useSWR<Cuenta[]>("/cuentas");
  if (!data) return <div className="esqueleto h-10 w-full" />;
  const cuentas = data.filter((c) => c.tipo !== "tarjeta_credito" && !c.archivada && (!moneda || c.moneda === moneda));
  if (!cuentas.length) return <p className="text-sm text-muted">Primero creá tus cuentas en Cuentas.</p>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {cuentas.map((c) => (
        <Chip key={c.id} activo={valor === c.id} onClick={() => onCambio(c.id)}>
          {c.nombre}
        </Chip>
      ))}
    </div>
  );
}

/** Gasto o ingreso, para cuando el texto no lo deja claro. */
export function TipoToggle({ valor, onCambio }: { valor: "gasto" | "ingreso"; onCambio: (t: "gasto" | "ingreso") => void }) {
  return (
    <div role="radiogroup" aria-label="Tipo" className="inline-flex rounded-full bg-surface-2 p-0.5">
      {(["gasto", "ingreso"] as const).map((t) => (
        <button key={t} type="button" role="radio" aria-checked={valor === t} onClick={() => onCambio(t)}
          className={cx("press min-h-7 rounded-full px-2.5 text-[12px] font-bold", valor === t ? (t === "ingreso" ? "bg-ok text-white" : "bg-ink text-ground") : "text-muted")}>
          {t === "gasto" ? "Gasto" : "Ingreso"}
        </button>
      ))}
    </div>
  );
}

/** Categorías como fila deslizable de íconos (reemplaza al select). */
export function CategoriaPicker({
  valor,
  tipo,
  onCambio,
}: {
  valor: string | null;
  tipo: "gasto" | "ingreso";
  onCambio: (id: string) => void;
}) {
  const { data } = useSWR<Categoria[]>("/categorias");
  const lista = data?.filter((c) => c.tipo === tipo) ?? [];
  return (
    <div className="no-scrollbar -mx-5 flex gap-2 overflow-x-auto px-5 pb-1" role="radiogroup" aria-label="Categoría">
      {lista.map((c) => {
        const activo = valor === c.id;
        return (
          <button
            key={c.id}
            role="radio"
            aria-checked={activo}
            onClick={() => onCambio(c.id)}
            className={cx(
              "press flex w-[76px] shrink-0 flex-col items-center gap-1.5 rounded-2xl border px-1 py-2.5 text-[11px] leading-tight font-bold",
              activo ? "border-ink bg-surface" : "border-transparent"
            )}
          >
            <IconoCat icono={c.icono} color={c.color} size={38} />
            <span className="line-clamp-2 text-center">{c.nombre}</span>
          </button>
        );
      })}
    </div>
  );
}

/** Hoy / Ayer / Anteayer / otra fecha, sin el date picker como primera opción. */
export function FechaChips({ valor, onCambio }: { valor: string; onCambio: (iso: string) => void }) {
  const hoy = hoyISO();
  const opciones = [
    { iso: hoy, label: "Hoy" },
    { iso: sumarDias(hoy, -1), label: "Ayer" },
    { iso: sumarDias(hoy, -2), label: "Anteayer" },
  ];
  const otra = !opciones.some((o) => o.iso === valor);
  const ref = useRef<HTMLInputElement>(null);
  const [manual, setManual] = useState(false);
  return (
    <div className="flex flex-wrap gap-1.5">
      {opciones.map((o) => (
        <Chip key={o.iso} activo={valor === o.iso} onClick={() => onCambio(o.iso)}>
          {o.label}
        </Chip>
      ))}
      <span className="relative inline-flex">
        <button
          type="button"
          onClick={() => {
            const i = ref.current;
            if (!i) return;
            // El calendario del sistema: showPicker en los navegadores nuevos; si no, el campo visible
            try {
              if (typeof i.showPicker === "function") return i.showPicker();
            } catch {
              /* sigue abajo */
            }
            setManual(true);
            window.setTimeout(() => ref.current?.focus(), 0);
          }}
          className={cx(
            "press inline-flex min-h-10 items-center gap-1.5 rounded-full border px-3.5 text-[13px] font-bold",
            otra ? "border-ink bg-ink text-ground" : "border-line-strong bg-surface"
          )}
          aria-label="Elegir otra fecha"
        >
          <CalendarDays size={15} />
          {otra ? new Date(valor + "T12:00:00").toLocaleDateString("es-AR", { day: "numeric", month: "short" }) : "Otra"}
        </button>
        <input
          ref={ref}
          type="date"
          value={valor}
          max={hoy}
          onChange={(e) => {
            if (e.target.value) onCambio(e.target.value);
            setManual(false);
          }}
          onBlur={() => setManual(false)}
          tabIndex={manual ? 0 : -1}
          aria-hidden={!manual}
          className={manual
            ? "absolute top-full left-0 z-10 mt-1 min-h-11 rounded-xl border border-line-strong bg-surface px-3 font-bold shadow-soft"
            : "pointer-events-none absolute bottom-0 left-0 h-px w-px opacity-0"}
        />
      </span>
    </div>
  );
}

/** Lista de opciones como filas tocables (reemplaza selects de cuentas). */
export function OpcionesLista<T extends { id: string }>({
  opciones,
  valor,
  onCambio,
  render,
}: {
  opciones: T[];
  valor: string;
  onCambio: (id: string) => void;
  render: (o: T) => React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5" role="radiogroup">
      {opciones.map((o) => (
        <button
          key={o.id}
          role="radio"
          aria-checked={valor === o.id}
          onClick={() => onCambio(o.id)}
          className={cx(
            "press flex min-h-14 items-center gap-3 rounded-2xl border bg-surface px-3 text-left",
            valor === o.id ? "border-ink" : "border-transparent"
          )}
        >
          {render(o)}
        </button>
      ))}
    </div>
  );
}
