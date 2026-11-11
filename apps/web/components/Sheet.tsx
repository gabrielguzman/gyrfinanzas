"use client";

import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

/** Hoja que sube desde abajo en el celu; ventana centrada en la compu. */
export function Sheet({
  abierto,
  onCerrar,
  titulo,
  children,
  ancho = "max-w-lg",
}: {
  abierto: boolean;
  onCerrar: () => void;
  titulo?: string;
  children: ReactNode;
  ancho?: string;
}) {
  useEffect(() => {
    if (!abierto) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onCerrar();
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [abierto, onCerrar]);

  // Se monta en <body>: dentro de una página animada (transform), `fixed` quedaría
  // relativo a la página y el modal aparecería corrido o fuera de la pantalla.
  const [montado, setMontado] = useState(false);
  useEffect(() => setMontado(true), []);

  if (!abierto || !montado) return null;
  return createPortal(
    <div className="anim-aparecer fixed inset-0 z-50 flex items-end justify-center bg-[var(--overlay)] lg:items-center lg:p-6" role="dialog" aria-modal="true" aria-label={titulo}>
      <button aria-label="Cerrar" onClick={onCerrar} className="absolute inset-0 h-full w-full cursor-default" tabIndex={-1} />
      <div
        className={`anim-subir safe-bottom relative flex max-h-[92dvh] w-full ${ancho} flex-col gap-4 overflow-y-auto rounded-t-[28px] bg-ground px-5 pt-3 pb-7 shadow-soft lg:rounded-[28px] lg:pt-6`}
      >
        <div className="h-1.5 w-10 shrink-0 self-center rounded-full bg-line-strong lg:hidden" />
        {titulo && (
          <div className="flex items-center justify-between gap-3">
            <h2 className="display text-[26px] leading-tight font-bold">{titulo}</h2>
            <button onClick={onCerrar} aria-label="Cerrar" className="press hidden h-10 w-10 items-center justify-center rounded-full bg-surface text-muted lg:flex">
              <X size={18} />
            </button>
          </div>
        )}
        {children}
      </div>
    </div>,
    document.body
  );
}
