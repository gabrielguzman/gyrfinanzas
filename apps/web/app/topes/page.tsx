"use client";

import { useState } from "react";
import useSWR from "swr";
import { Gauge, X } from "lucide-react";
import { BarraTope } from "@/components/Topes";
import { useApp } from "@/components/Shell";
import { Esqueleto, IconoCat, Lista, Seccion, Titulo, cx } from "@/components/ui";
import { api, type Tope } from "@/lib/api";
import { monto, nombreMes } from "@/lib/format";

const pesos = (v: string | number) => monto(Math.round(Number(v)));

function FilaEditable({ t, onGuardar }: { t: Tope; onGuardar: (monto: number | null) => Promise<void> }) {
  const [valor, setValor] = useState(t.tope ? String(Math.round(Number(t.tope))) : "");
  const [ocupado, setOcupado] = useState(false);
  const guardar = async (v: number | null) => {
    setOcupado(true);
    await onGuardar(v);
    setOcupado(false);
  };
  const actual = t.tope ? Math.round(Number(t.tope)) : null;
  const nuevo = valor ? Number(valor) : null;
  return (
    <div className="flex flex-col gap-2 px-4 py-3">
      <div className="flex items-center gap-3">
        <IconoCat icono={t.icono} color={t.color} size={36} />
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="truncate text-[15px] font-bold">{t.categoria}</span>
          <span className="text-[12px] text-muted">
            Este mes <span className="num whitespace-nowrap">{pesos(t.gastado)}</span>
            {Number(t.promedio) > 0 && <> · solés gastar <span className="num whitespace-nowrap">{pesos(t.promedio)}</span></>}
          </span>
        </span>
        <label className="flex min-h-10 w-[112px] shrink-0 items-center gap-1 rounded-xl border border-line-strong bg-surface px-2.5">
          <span className="text-sm font-bold text-faint">$</span>
          <input
            inputMode="numeric"
            value={valor}
            placeholder="sin tope"
            aria-label={`Tope de ${t.categoria}`}
            onChange={(e) => setValor(e.target.value.replace(/\D/g, ""))}
            onBlur={() => nuevo !== actual && guardar(nuevo)}
            onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
            className="num w-full bg-transparent text-[14px] font-bold outline-none placeholder:font-semibold placeholder:text-faint"
          />
        </label>
        {actual !== null && (
          <button aria-label={`Sacar tope de ${t.categoria}`} disabled={ocupado} onClick={() => { setValor(""); guardar(null); }}
            className="press flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-faint hover:bg-surface-2"><X size={16} /></button>
        )}
      </div>
      {actual === null && t.sugerido && (
        <button disabled={ocupado} onClick={() => { setValor(String(Math.round(Number(t.sugerido)))); guardar(Number(t.sugerido)); }}
          className="press ml-12 w-fit rounded-full bg-surface-2 px-3 py-1 text-[12px] font-bold text-muted">
          Usar {pesos(t.sugerido!)}
        </button>
      )}
    </div>
  );
}

export default function TopesPage() {
  const { data, mutate } = useSWR<Tope[]>("/topes?todas=true");
  const { aviso, refrescar } = useApp();
  if (!data) return <Esqueleto className="h-96 rounded-[28px]" />;
  const con = data.filter((t) => t.tope);
  const sin = data.filter((t) => !t.tope).sort((a, b) => Number(b.promedio) - Number(a.promedio) || Number(b.gastado) - Number(a.gastado));
  const total = con.reduce((a, t) => a + Number(t.tope), 0);
  const gastado = con.reduce((a, t) => a + Number(t.gastado), 0);

  async function guardar(t: Tope, valor: number | null) {
    await api.put(`/topes/${t.categoria_id}`, { monto: valor });
    aviso(valor ? `Tope de ${t.categoria}: ${pesos(valor)} por mes` : `Sacaste el tope de ${t.categoria}`);
    mutate();
    refrescar();
  }

  return (
    <div className="flex flex-col gap-7 lg:max-w-3xl">
      <Titulo>Topes</Titulo>

      {con.length > 0 ? (
        <section className="flex flex-col gap-5 rounded-[28px] bg-surface p-6 shadow-soft">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div className="flex flex-col gap-1">
              <span className="text-sm font-semibold text-muted">En {nombreMes()} llevás</span>
              <span className="display num text-[38px] leading-none font-bold">{pesos(gastado)}</span>
            </div>
            <span className="text-sm text-muted">de <b className="num text-ink">{pesos(total)}</b> que te propusiste</span>
          </div>
          {con.map((t) => <BarraTope key={t.categoria_id} t={t} />)}
        </section>
      ) : (
        <section className="flex items-start gap-3 rounded-[24px] border-2 border-dashed border-accent/40 bg-accent-soft/50 p-5">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[14px] bg-accent text-accent-ink"><Gauge size={19} /></span>
          <div className="flex flex-col gap-0.5">
            <b>Poné un techo a lo que más se te va</b>
            <span className="text-sm text-muted">Te aviso cuando llegues al 80% y si te pasás, y te muestro cómo cerrarías el mes a este ritmo. Abajo tenés lo que solés gastar en cada una para arrancar.</span>
          </div>
        </section>
      )}

      <Seccion titulo={con.length ? "Cambiar topes" : "Elegí en cuáles"}>
        <Lista>
          {[...con, ...sin].map((t) => <FilaEditable key={t.categoria_id + (t.tope ?? "")} t={t} onGuardar={(v) => guardar(t, v)} />)}
        </Lista>
        <p className={cx("text-[13px] text-muted")}>El mes es de calendario. Las compras en cuotas cuentan por su cuota de cada mes.</p>
      </Seccion>
    </div>
  );
}
