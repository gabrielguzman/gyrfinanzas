"use client";

import { useState } from "react";
import useSWR from "swr";
import { ChevronDown, Plus } from "lucide-react";
import { GarantiaFila, cuandoVence } from "@/components/Garantias";
import { useApp } from "@/components/Shell";
import { Boton, Esqueleto, Lista, Seccion, Titulo, Vacio, cx } from "@/components/ui";
import type { Garantia } from "@/lib/api";
import { monto } from "@/lib/format";
import { useContador } from "@/lib/hooks";

export default function GarantiasPage() {
  const { abrirGarantia } = useApp();
  const { data } = useSWR<Garantia[]>("/garantias");
  const [verVencidas, setVerVencidas] = useState(false);
  const vivas = (data ?? []).filter((g) => g.estado !== "vencida");
  const cubierto = vivas.reduce((s, g) => s + Number(g.monto ?? 0), 0);
  const animado = useContador(cubierto);

  const grupos: { titulo: string; items: Garantia[] }[] = [
    { titulo: "Por vencer", items: vivas.filter((g) => g.estado === "por_vencer") },
    { titulo: "En reparación", items: vivas.filter((g) => g.estado === "en_reparacion") },
    { titulo: "Vigentes", items: vivas.filter((g) => g.estado === "vigente") },
  ];
  const vencidas = (data ?? []).filter((g) => g.estado === "vencida");
  const proxima = vivas.find((g) => g.estado !== "en_reparacion");
  const abrir = (g: Garantia) => abrirGarantia({ id: g.id });

  return (
    <div className="flex flex-col gap-7">
      <Titulo extra={<Boton variante="acento" onClick={() => abrirGarantia({ nueva: true })}><Plus size={18} /> Agregar</Boton>}>
        Garantías
      </Titulo>

      {!data ? (
        <Esqueleto className="h-72 rounded-[28px]" />
      ) : !data.length ? (
        <Vacio
          titulo="Ninguna garantía cargada"
          accion={<Boton variante="acento" onClick={() => abrirGarantia({ nueva: true })}><Plus size={18} /> Agregar la primera</Boton>}
        >
          Cuando cargues una compra, sumale cuánto dura la garantía:{" "}
          <b className="text-ink">heladera 850k visa garantía 1 año</b>. Te aviso un mes antes de que venza, con la factura a mano.
        </Vacio>
      ) : (
        <div className="grid grid-cols-1 gap-7 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] lg:items-start lg:gap-10">
          <section className="flex flex-col gap-5 rounded-[28px] bg-slab p-6 text-slab-ink shadow-soft lg:sticky lg:top-10 lg:p-8">
            <div>
              <p className="text-sm text-slab-muted">{vivas.length === 1 ? "1 cosa con garantía" : `${vivas.length} cosas con garantía`}</p>
              {cubierto > 0 && (
                <>
                  <p className="display num text-[clamp(40px,11vw,52px)] leading-[0.95] font-bold">{monto(Math.round(animado))}</p>
                  <p className="mt-2 text-sm text-slab-muted">en compras cubiertas si algo se rompe.</p>
                </>
              )}
            </div>
            {proxima && (
              <p className="rounded-2xl bg-white/8 p-3 text-sm">
                La próxima en vencer: <b>{proxima.producto}</b>. {cuandoVence(proxima)}.
              </p>
            )}
            <p className="text-sm text-slab-muted">
              Si lo mandás a reparar, avisame: los días en el service se suman a la garantía.
            </p>
          </section>

          <div className="flex min-w-0 flex-col gap-7">
            {grupos.filter((gr) => gr.items.length).map((gr) => (
              <Seccion key={gr.titulo} titulo={gr.titulo}>
                <Lista>{gr.items.map((g) => <GarantiaFila key={g.id} g={g} onAbrir={() => abrir(g)} />)}</Lista>
              </Seccion>
            ))}
            {vencidas.length > 0 && (
              <div className="flex flex-col gap-3">
                <button onClick={() => setVerVencidas((v) => !v)} className="press flex w-fit items-center gap-1.5 text-sm font-bold text-muted" aria-expanded={verVencidas}>
                  {vencidas.length === 1 ? "1 vencida" : `${vencidas.length} vencidas`}
                  <ChevronDown size={16} className={cx("transition-transform", verVencidas && "rotate-180")} />
                </button>
                {verVencidas && <Lista>{vencidas.map((g) => <GarantiaFila key={g.id} g={g} onAbrir={() => abrir(g)} />)}</Lista>}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
