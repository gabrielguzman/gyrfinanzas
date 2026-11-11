"use client";

import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import { Plus } from "lucide-react";
import { DeudaSheet, NuevaDeudaSheet, iconoDeuda } from "@/components/Deudas";
import { SaldoDeudasChart } from "@/components/Graficos";
import { Boton, Chip, Esqueleto, IconoCat, Lista, Mensaje, Seccion, Titulo, Vacio, cx, inputCls } from "@/components/ui";
import { api, type Deuda, type Simulacion, type Tarjeta } from "@/lib/api";
import { fechaCorta, MESES, monto } from "@/lib/format";
import { useContador } from "@/lib/hooks";

const EXTRAS = [0, 20000, 50000, 100000];
const EXPLICA = {
  avalancha: "Ponés todo lo que sobra en la deuda con la tasa más alta. Es la que menos intereses te cobra en total.",
  bola_de_nieve: "Ponés todo lo que sobra en la deuda más chica. Cerrás deudas rápido y ese envión ayuda a seguir.",
};

function mesAnio(iso: string | null) {
  if (!iso) return "—";
  const d = new Date(iso + "T12:00:00");
  return `${MESES[d.getMonth()]} ${d.getFullYear()}`;
}

function Total({ etiqueta, valor, tono }: { etiqueta: string; valor: number; tono?: "ok" }) {
  const v = useContador(valor);
  return (
    <div className="flex flex-col gap-1">
      <span className="text-sm font-semibold text-muted">{etiqueta}</span>
      <span className={cx("display num text-[40px] leading-none font-bold", tono === "ok" && "text-ok")}>{monto(Math.round(v))}</span>
    </div>
  );
}

function FilaDeuda({ d, onAbrir }: { d: Deuda; onAbrir: () => void }) {
  const [icono, color] = iconoDeuda(d);
  let sub = "";
  if (d.tipo === "prestamo") {
    const partes = [];
    if (d.cuotas_total) partes.push(`Cuota ${(d.cuotas_pagadas ?? 0) + 1} de ${d.cuotas_total}`);
    if (d.cuota) partes.push(`${monto(d.cuota)}/mes`);
    if (d.proximo_vencimiento) partes.push(`vence el ${fechaCorta(d.proximo_vencimiento)}`);
    sub = partes.join(" · ");
  } else if (d.tipo === "debo") {
    sub = d.tna ? `TNA ${Number(d.tna)}%` : "Sin interés";
  } else {
    const dias = Math.round((Date.now() - new Date(d.fecha_alta + "T12:00:00").getTime()) / 86400000);
    sub = dias > 1 ? `Hace ${dias} días` : "Desde hoy";
  }
  const progreso = d.tipo === "prestamo" && d.cuotas_total ? (d.cuotas_pagadas ?? 0) / d.cuotas_total : null;
  return (
    <button onClick={onAbrir} className="press flex w-full flex-col gap-2 bg-surface px-4 py-3.5 text-left hover:bg-surface-2">
      <span className="flex items-center gap-3">
        <IconoCat icono={icono} color={color} />
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="truncate text-[15px] font-bold">{d.nombre}</span>
          <span className="truncate text-[13px] text-muted">{sub}</span>
        </span>
        <span className={cx("num shrink-0 font-extrabold", d.tipo === "me_deben" && "text-ok")}>{monto(d.saldo, d.moneda)}</span>
      </span>
      {progreso != null && (
        <span className="ml-[52px] h-1.5 overflow-hidden rounded-full bg-surface-2" aria-hidden>
          <span className="block h-full rounded-full bg-accent" style={{ width: `${progreso * 100}%` }} />
        </span>
      )}
    </button>
  );
}

function Plan({ tarjetas }: { tarjetas: Tarjeta[] }) {
  const [estrategia, setEstrategia] = useState<"avalancha" | "bola_de_nieve">("avalancha");
  const [extra, setExtra] = useState(20000);
  const [extraTexto, setExtraTexto] = useState("");
  const [inflacion, setInflacion] = useState("");
  const [conTarjetas, setConTarjetas] = useState<string[]>([]);
  const [sim, setSim] = useState<Simulacion | null>(null);

  const cuerpo = useMemo(() => {
    const inf = Number(inflacion.replace(",", "."));
    return JSON.stringify({ extra_mensual: String(extra), inflacion_mensual: inflacion && inf >= 0 ? String(inf) : null, tarjetas: conTarjetas });
  }, [extra, inflacion, conTarjetas]);

  useEffect(() => {
    const t = window.setTimeout(async () => {
      try {
        setSim(await api.post<Simulacion>("/deudas/simular", JSON.parse(cuerpo)));
      } catch {
        setSim(null);
      }
    }, 250);
    return () => window.clearTimeout(t);
  }, [cuerpo]);

  const conDeuda = tarjetas.filter((t) => Number(t.deuda) > 0);
  if (!sim) return <Esqueleto className="h-96 rounded-[22px]" />;
  if (!sim.deudas.length && !conDeuda.length) return null;

  const r = sim[estrategia];
  const otra = sim[estrategia === "avalancha" ? "bola_de_nieve" : "avalancha"];
  const total = sim.deudas.reduce((a, d) => a + Number(d.saldo), 0);
  const ahorro = Number(sim.bola_de_nieve.intereses) - Number(sim.avalancha.intereses);
  const primeraBola = sim.bola_de_nieve.orden[0];
  const primeraAv = sim.avalancha.orden[0];

  let comparacion = "";
  if (r.meses && otra.meses) {
    if (estrategia === "avalancha" && ahorro > 0) comparacion = `Pagás ${monto(Math.round(ahorro))} menos de intereses que con bola de nieve.`;
    if (estrategia === "bola_de_nieve" && primeraBola && primeraAv && primeraBola.mes < primeraAv.mes)
      comparacion = `Cerrás tu primera deuda (${primeraBola.nombre}) en el mes ${primeraBola.mes}, antes que con avalancha. A cambio, pagás ${monto(Math.round(ahorro))} más de intereses.`;
    else if (estrategia === "bola_de_nieve" && ahorro > 0) comparacion = `Pagás ${monto(Math.round(ahorro))} más de intereses que con avalancha.`;
  }

  return (
    <Seccion titulo="Plan para salir">
      <div className="grid grid-cols-2 gap-1 rounded-2xl bg-surface-2 p-1" role="radiogroup" aria-label="Estrategia">
        {(["avalancha", "bola_de_nieve"] as const).map((e) => (
          <button
            key={e}
            role="radio"
            aria-checked={estrategia === e}
            onClick={() => setEstrategia(e)}
            className={cx("press min-h-11 rounded-xl text-sm font-bold", estrategia === e ? "bg-surface text-ink shadow-soft" : "text-muted")}
          >
            {e === "avalancha" ? "Avalancha" : "Bola de nieve"}
          </button>
        ))}
      </div>
      <p className="text-sm text-muted">{EXPLICA[estrategia]}</p>

      <div className="flex flex-col gap-5 rounded-[22px] bg-surface p-5 shadow-soft">
        {r.meses ? (
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-muted">Sin deudas en</p>
              <p className="display text-[38px] leading-none font-bold text-accent">{mesAnio(r.fecha_fin)}</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-muted">Intereses que vas a pagar</p>
              <p className="num text-lg font-extrabold">{monto(Math.round(Number(r.intereses)))}</p>
            </div>
          </div>
        ) : (
          <Mensaje>Con estos pagos las deudas no bajan: los intereses le ganan a lo que pagás. Sumá un extra por mes.</Mensaje>
        )}
        {comparacion && <p className="text-sm font-semibold">{comparacion}</p>}
        {r.meses && otra.meses && (
          <SaldoDeudasChart
            a={r.serie.map(Number)}
            b={otra.serie.map(Number)}
            nombreA={estrategia === "avalancha" ? "Avalancha" : "Bola de nieve"}
            nombreB={estrategia === "avalancha" ? "Bola de nieve" : "Avalancha"}
            inicio={total}
          />
        )}

        <div className="flex flex-col gap-2">
          <span className="text-[13px] font-bold">Extra por mes, además de las cuotas</span>
          <div className="flex flex-wrap gap-1.5">
            {EXTRAS.map((v) => (
              <Chip key={v} activo={extra === v && !extraTexto} onClick={() => { setExtra(v); setExtraTexto(""); }}>
                {v ? `+${monto(v)}` : "Nada"}
              </Chip>
            ))}
            <input
              value={extraTexto}
              onChange={(e) => {
                setExtraTexto(e.target.value);
                const n = Number(e.target.value.replace(/\./g, "").replace(",", "."));
                if (n >= 0) setExtra(n);
              }}
              inputMode="numeric"
              placeholder="Otro"
              aria-label="Otro monto extra por mes"
              className={cx("min-h-10 w-24 rounded-full border px-3.5 text-[13px] font-bold outline-none", extraTexto ? "border-ink" : "border-line-strong", "bg-surface")}
            />
          </div>
          <span className="text-xs text-faint">Presupuesto total por mes: {monto(sim.presupuesto_mensual)}</span>
        </div>

        {conDeuda.length > 0 && (
          <div className="flex flex-col gap-2">
            <span className="text-[13px] font-bold">¿Financiás alguna tarjeta?</span>
            <div className="flex flex-wrap gap-1.5">
              {conDeuda.map((t) => (
                <Chip
                  key={t.cuenta_id}
                  activo={conTarjetas.includes(t.cuenta_id)}
                  onClick={() => setConTarjetas((c) => (c.includes(t.cuenta_id) ? c.filter((x) => x !== t.cuenta_id) : [...c, t.cuenta_id]))}
                >
                  {t.nombre} · {monto(t.deuda)}
                </Chip>
              ))}
            </div>
            <span className="text-xs text-faint">Sumala solo si no la pagás completa: se simula con la TNA y el mínimo de su último resumen.</span>
          </div>
        )}

        <label className="flex flex-col gap-1.5">
          <span className="text-[13px] font-bold">Inflación mensual esperada (opcional)</span>
          <span className="flex items-center gap-2">
            <input value={inflacion} onChange={(e) => setInflacion(e.target.value)} inputMode="decimal" placeholder="Ej. 2,5" className={inputCls + " num w-28"} />
            <span className="text-sm font-bold text-muted">%</span>
          </span>
          <span className="text-xs text-faint">Con este dato ordeno por tasa real: una deuda en pesos a tasa fija más baja que la inflación se achica sola.</span>
        </label>
      </div>

      {r.orden.length > 0 && (
        <div className="flex flex-col gap-2">
          <h3 className="font-extrabold">Orden de pago</h3>
          <ol className="overflow-hidden rounded-[22px] bg-surface shadow-soft [&>*+*]:border-t [&>*+*]:border-line">
            {r.orden.map((p, i) => {
              const d = sim.deudas.find((x) => x.id === p.id);
              const real = d?.tasa_real_anual != null ? Number(d.tasa_real_anual) : null;
              return (
                <li key={p.id} className="flex items-center gap-3 px-4 py-3">
                  <span className={cx("flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-extrabold", i === 0 ? "bg-accent text-accent-ink" : "bg-surface-2 text-muted")}>{i + 1}</span>
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate font-bold">{p.nombre}</span>
                    <span className="text-[13px] text-muted">
                      {d && Number(d.tasa_anual) > 0 ? `TNA ${Number(d.tasa_anual)}%` : "Sin interés"}
                      {real != null && (real < 0 ? " · la inflación la achica" : ` · real ${real.toLocaleString("es-AR")}%`)}
                    </span>
                  </span>
                  <span className="shrink-0 text-right text-[13px]">
                    <span className="block text-muted">la terminás en</span>
                    <b>{mesAnio(p.fecha)}</b>
                  </span>
                </li>
              );
            })}
          </ol>
          <p className="text-xs text-faint">Cálculo aproximado en pesos de hoy, con la TNA y la cuota de cada deuda.</p>
        </div>
      )}
    </Seccion>
  );
}

export default function DeudasPage() {
  const { data: deudas } = useSWR<Deuda[]>("/deudas");
  const { data: tarjetas } = useSWR<Tarjeta[]>("/tarjetas");
  const [nueva, setNueva] = useState(false);
  const [abierta, setAbierta] = useState<string | null>(null);

  const debo = deudas?.filter((d) => d.tipo !== "me_deben") ?? [];
  const meDeben = deudas?.filter((d) => d.tipo === "me_deben") ?? [];
  const totalDebo = debo.filter((d) => d.moneda === "ARS").reduce((a, d) => a + Number(d.saldo), 0);
  const totalMeDeben = meDeben.filter((d) => d.moneda === "ARS").reduce((a, d) => a + Number(d.saldo), 0);

  return (
    <div className="flex flex-col gap-7">
      <Titulo extra={<Boton variante="linea" onClick={() => setNueva(true)}><Plus size={18} /> Nueva</Boton>}>Deudas</Titulo>

      {!deudas ? (
        <Esqueleto className="h-24" />
      ) : deudas.length === 0 ? (
        <Vacio
          titulo="No tenés deudas cargadas"
          accion={<Boton variante="acento" onClick={() => setNueva(true)}><Plus size={18} /> Cargar una</Boton>}
        >
          Cargá préstamos con cuotas, lo que le debés a alguien o lo que te deben. También podés escribir en la carga rápida «le presté 20 lucas a juan».
        </Vacio>
      ) : (
        <div className="flex flex-wrap gap-x-12 gap-y-5">
          <Total etiqueta="Debés" valor={totalDebo} />
          {meDeben.length > 0 && <Total etiqueta="Te deben" valor={totalMeDeben} tono="ok" />}
        </div>
      )}

      <div className="grid grid-cols-1 gap-7 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] lg:items-start lg:gap-10">
        <div className="flex min-w-0 flex-col gap-7">
          {deudas && tarjetas && <Plan tarjetas={tarjetas} />}
        </div>
        <div className="flex min-w-0 flex-col gap-7">
          {debo.length > 0 && (
            <Seccion titulo="Lo que debés">
              <Lista>{debo.map((d) => <FilaDeuda key={d.id} d={d} onAbrir={() => setAbierta(d.id)} />)}</Lista>
            </Seccion>
          )}
          {meDeben.length > 0 && (
            <Seccion titulo="Te deben">
              <Lista>{meDeben.map((d) => <FilaDeuda key={d.id} d={d} onAbrir={() => setAbierta(d.id)} />)}</Lista>
            </Seccion>
          )}
        </div>
      </div>

      <NuevaDeudaSheet abierto={nueva} onCerrar={() => setNueva(false)} />
      <DeudaSheet id={abierta} onCerrar={() => setAbierta(null)} />
    </div>
  );
}
