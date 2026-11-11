"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";
import { ICONOS } from "@/lib/categorias";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

type Variante = "primario" | "acento" | "linea" | "fantasma" | "peligro";

export function Boton({
  variante = "primario",
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variante?: Variante }) {
  const estilos: Record<Variante, string> = {
    primario: "bg-ink text-ground",
    acento: "bg-accent text-accent-ink",
    linea: "bg-surface text-ink border border-line-strong",
    fantasma: "bg-transparent text-ink border border-dashed border-line-strong",
    peligro: "bg-surface text-danger border border-line-strong",
  };
  return (
    <button
      {...rest}
      className={cx(
        "press inline-flex min-h-11 items-center justify-center gap-2 rounded-2xl px-4 text-sm font-bold disabled:opacity-40",
        estilos[variante],
        className
      )}
    >
      {children}
    </button>
  );
}

export function Chip({
  activo,
  onClick,
  children,
  className,
  disabled,
}: {
  activo?: boolean;
  onClick?: () => void;
  children: ReactNode;
  className?: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={activo}
      className={cx(
        "press inline-flex min-h-10 items-center gap-1.5 whitespace-nowrap rounded-full border px-3.5 text-[13px] font-bold disabled:opacity-40",
        activo ? "border-ink bg-ink text-ground" : "border-line-strong bg-surface text-ink",
        className
      )}
    >
      {children}
    </button>
  );
}

/** Ícono de categoría (o de cuenta) en un cuadrado con su color. */
export function IconoCat({
  icono,
  color,
  size = 40,
  className,
}: {
  icono?: string | null;
  color?: string | null;
  size?: number;
  className?: string;
}) {
  const Icono = ICONOS[icono || "otros"] ?? ICONOS.otros;
  return (
    <span
      data-cat={color || "slate"}
      className={cx("inline-flex shrink-0 items-center justify-center", className)}
      style={{
        width: size,
        height: size,
        borderRadius: size * 0.34,
        background: "var(--cat-bg)",
        color: "var(--cat-fg)",
      }}
      aria-hidden
    >
      <Icono size={Math.round(size * 0.5)} strokeWidth={2.1} />
    </span>
  );
}

export function Campo({ label, children, ayuda }: { label: string; children: ReactNode; ayuda?: string }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[13px] font-semibold text-muted">{label}</span>
      {children}
      {ayuda && <span className="text-xs text-faint">{ayuda}</span>}
    </label>
  );
}

export const inputCls =
  "min-h-12 w-full rounded-2xl border border-line-strong bg-surface px-4 text-base font-semibold text-ink outline-none placeholder:text-faint focus:border-accent";

export function Titulo({ children, extra }: { children: ReactNode; extra?: ReactNode }) {
  return (
    <div className="flex items-end justify-between gap-3">
      <h1 className="display text-[34px] leading-none font-bold">{children}</h1>
      {extra}
    </div>
  );
}

export function Seccion({
  titulo,
  extra,
  children,
  className,
}: {
  titulo: string;
  extra?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cx("flex flex-col gap-3", className)}>
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-[17px] font-extrabold">{titulo}</h2>
        {extra}
      </div>
      {children}
    </section>
  );
}

/** Contenedor de lista: filas separadas por líneas, no tarjetas sueltas. */
export function Lista({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cx("overflow-hidden rounded-[22px] bg-surface shadow-soft [&>*+*]:border-t [&>*+*]:border-line", className)}>
      {children}
    </div>
  );
}

export function Vacio({ titulo, children, accion }: { titulo: string; children?: ReactNode; accion?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-2 rounded-[22px] border border-dashed border-line-strong p-5">
      <p className="font-bold">{titulo}</p>
      {children && <p className="text-sm text-muted">{children}</p>}
      {accion}
    </div>
  );
}

export function Esqueleto({ className }: { className?: string }) {
  return <div className={cx("esqueleto", className)} aria-hidden />;
}

export function Mensaje({ children, tono = "aviso" }: { children: ReactNode; tono?: "aviso" | "error" }) {
  return (
    <p
      role="alert"
      className={cx(
        "rounded-2xl p-3 text-sm font-semibold",
        tono === "error" ? "bg-danger-soft text-danger" : "bg-warn-soft text-warn-ink"
      )}
    >
      {children}
    </p>
  );
}
