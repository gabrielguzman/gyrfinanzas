"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useSWRConfig } from "swr";
import { Bug, Copy, Repeat, TrendingUp, X, Percent, Coffee, ShieldAlert, ShieldPlus, Target, Landmark } from "lucide-react";
import { api, type Hallazgo } from "@/lib/api";
import { useApp } from "./Shell";
import { cx } from "./ui";

const ICONO: Record<Hallazgo["tipo"], typeof Bug> = {
  duplicado: Copy,
  suscripcion_aumento: TrendingUp,
  plata_tirada: Percent,
  hormiga: Coffee,
  desvio: TrendingUp,
  fijos: Repeat,
  garantia: ShieldAlert,
  sin_garantia: ShieldPlus,
  meta: Target,
  inversion: Landmark,
};
const ACCION: Record<string, string> = {
  categoria: "Ver gastos", movimiento: "Revisar", buscar: "Ver", garantia: "Ver garantía", garantia_nueva: "Cargar garantía", link: "Ver",
};

export function HallazgoFila({ h }: { h: Hallazgo }) {
  const router = useRouter();
  const { mutate } = useSWRConfig();
  const { aviso, abrirMovimiento, abrirGarantia } = useApp();
  const [oculto, setOculto] = useState(false);
  const Icono = ICONO[h.tipo] ?? Bug;
  if (oculto) return null;

  function accion() {
    if (!h.accion) return;
    if (h.accion.tipo === "movimiento") abrirMovimiento(h.accion.valor);
    else if (h.accion.tipo === "garantia") abrirGarantia({ id: h.accion.valor });
    else if (h.accion.tipo === "link") router.push(h.accion.valor);
    else if (h.accion.tipo === "garantia_nueva") abrirGarantia({ nueva: true, movimiento: h.accion.valor });
    else if (h.accion.tipo === "categoria") router.push(`/movimientos?categoria=${h.accion.valor}`);
    else router.push(`/movimientos?q=${encodeURIComponent(h.accion.valor)}`);
  }

  async function descartar() {
    setOculto(true);
    await api.post("/hallazgos/descartar", { clave: h.clave });
    mutate((k) => typeof k === "string" && (k.startsWith("/hallazgos") || k.startsWith("/semana")));
    aviso("Listo, no te lo muestro más", {
      deshacer: async () => {
        await api.post("/hallazgos/restaurar", { clave: h.clave });
        setOculto(false);
      },
    });
  }

  return (
    <div className="flex gap-3 px-4 py-3.5">
      <span
        className={cx(
          "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl",
          h.tono === "aviso" ? "bg-warn-soft text-warn-ink" : "bg-accent-soft text-accent"
        )}
        aria-hidden
      >
        <Icono size={18} />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <p className="text-[15px] leading-snug font-bold">{h.titulo}</p>
        <p className="text-[13px] leading-snug text-muted">{h.detalle}</p>
        {h.accion && (
          <button onClick={accion} className="press mt-1 w-fit text-sm font-bold text-accent">
            {ACCION[h.accion.tipo]}
          </button>
        )}
      </div>
      <button onClick={descartar} aria-label={`No mostrar más: ${h.titulo}`} className="press -mt-1 -mr-2 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-faint hover:text-ink">
        <X size={17} />
      </button>
    </div>
  );
}
