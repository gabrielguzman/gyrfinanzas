"use client";

import useSWR from "swr";
import { Check, Flame } from "lucide-react";
import { api, type Racha } from "@/lib/api";
import { vibrar } from "@/lib/hooks";
import { useApp } from "./Shell";
import { cx } from "./ui";

const DIAS = ["D", "L", "M", "M", "J", "V", "S"];

/** Días seguidos con todo cargado. Suave: no reta, acompaña. */
export function RachaCard() {
  const { data, mutate } = useSWR<Racha>("/racha");
  const { aviso, refrescar } = useApp();
  if (!data) return <div className="esqueleto h-[118px] rounded-[22px]" />;

  const { actual, mejor, hoy, dias } = data;
  const titulo = actual === 0 ? "Empezá tu racha" : actual === 1 ? "1 día cargando todo" : `${actual} días seguidos`;
  const sub =
    hoy === "vacio"
      ? actual > 0 ? "Cargá lo de hoy para sumar uno más." : "Cargá lo que gastes hoy, o marcá que no gastaste."
      : mejor > actual ? `Tu mejor racha: ${mejor} días.` : actual >= 3 ? "Es tu mejor racha. 🎉" : "Hoy ya está.";

  async function sinGastos() {
    vibrar();
    mutate(await api.post<Racha>("/racha/sin-gastos", {}), { revalidate: false });
    aviso("Anotado: hoy no gastaste nada");
    refrescar();
  }

  return (
    <div className="flex flex-col gap-3.5 rounded-[22px] bg-surface p-4 shadow-soft">
      <div className="flex items-center gap-3">
        <span className={cx("flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px]", actual > 0 ? "bg-warn-soft text-warn" : "bg-surface-2 text-faint")}>
          <Flame size={22} fill={actual > 0 ? "currentColor" : "none"} />
        </span>
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="font-extrabold">{titulo}</span>
          <span className="text-[13px] text-muted">{sub}</span>
        </div>
        {hoy === "vacio" && (
          <button onClick={sinGastos} className="press min-h-10 shrink-0 rounded-xl border border-line-strong px-3 text-[13px] font-bold">
            Hoy no gasté
          </button>
        )}
      </div>
      <div className="flex justify-between gap-1" aria-label={`Últimos 14 días: ${dias.filter((d) => d.estado !== "vacio").length} con todo cargado`}>
        {dias.map((d, i) => {
          const f = new Date(d.fecha + "T12:00:00");
          const esHoy = i === dias.length - 1;
          return (
            <span key={d.fecha} className="flex flex-1 flex-col items-center gap-1">
              <span
                title={d.estado === "sin_gastos" ? "Sin gastos" : d.estado === "cargado" ? "Cargado" : "Nada cargado"}
                className={cx(
                  "flex aspect-square w-full max-w-7 items-center justify-center rounded-full",
                  d.estado === "cargado" && "bg-warn text-white",
                  d.estado === "sin_gastos" && "bg-warn-soft text-warn",
                  d.estado === "vacio" && "bg-surface-2",
                  esHoy && "ring-2 ring-ink ring-offset-2 ring-offset-[var(--surface)]"
                )}
              >
                {d.estado !== "vacio" && <Check size={12} strokeWidth={3.2} />}
              </span>
              <span className={cx("text-[10px] font-bold", esHoy ? "text-ink" : "text-faint")}>{DIAS[f.getDay()]}</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}
