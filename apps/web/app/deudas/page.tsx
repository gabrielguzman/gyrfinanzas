"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import { Plus } from "lucide-react";
import { DeudaSheet, NuevaDeudaSheet, iconoDeuda } from "@/components/Deudas";
import { SaldoDeudasChart } from "@/components/Graficos";
import { Boton, Chip, Esqueleto, IconoCat, Lista, Mensaje, Seccion, Titulo, Vacio, cx, inputCls } from "@/components/ui";
import { api, type Deuda, type Plan as PlanCuotas, type Simulacion, type Tarjeta } from "@/lib/api";
import { fechaCorta, MESES, monto, nombrePeriodo } from "@/lib/format";
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
  if (!sim.deudas.length && !conTarjetas.length) {
    // Sin deudas con interés: solo tiene sentido si financiás una tarjeta
    return (
      <Seccion titulo="Plan para salir">
        <div className="flex flex-col gap-3 rounded-[22px] bg-surface p-5 shadow-soft">
          <p className="text-sm text-muted">
            Tus deudas no tienen interés: con pagar las cuotas y el resumen completo alcanza. Si pagás el mínimo de una tarjeta, elegila y te muestro cómo salir y cuánto te cuesta.
          </p>
          <div className="flex flex-wrap gap-1.5">
            {conDeuda.map((t) => (
              <Chip key={t.cuenta_id} onClick={() => setConTarjetas([t.cuenta_id])}>Financio {t.nombre}</Chip>
            ))}
          </div>
        </div>
      </Seccion>
    );
  }

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
        {(r.meses ?? 0) > 0 && (otra.meses ?? 0) > 0 && (
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

const mesCorto = (per: string) => {
  const [a, m] = per.split("-").map(Number);
  return `${MESES[m - 1].slice(0, 3)} ${a}`;
};
const pesos = (v: number, moneda: "ARS" | "USD" = "ARS") => monto(Math.round(v), moneda);

function sumarPeriodo(p: string, n: number): string {
  const [a, m] = p.split("-").map(Number);
  const t = a * 12 + (m - 1) + n;
  return `${Math.floor(t / 12)}-${String((t % 12) + 1).padStart(2, "0")}`;
}
function distancia(desde: string, hasta: string): number {
  const [a1, m1] = desde.split("-").map(Number);
  const [a2, m2] = hasta.split("-").map(Number);
  return a2 * 12 + m2 - (a1 * 12 + m1);
}
const cuotaEn = (p: PlanCuotas, per: string) => {
  const k = distancia(p.primer_periodo, per) + 1;
  return k >= 1 && k <= p.cuotas_total;
};
/** Cuándo vence el resumen que cierra en el periodo (igual que en la API). */
function vencimiento(t: Tarjeta, per: string): Date {
  const [a, m] = per.split("-").map(Number);
  const dc = t.dia_cierre ?? 25;
  const cierre = new Date(a, m - 1, Math.min(dc, new Date(a, m, 0).getDate()));
  if (!t.dia_vencimiento) return new Date(cierre.getTime() + 10 * 86400000);
  const v = new Date(a, m - 1, Math.min(t.dia_vencimiento, new Date(a, m, 0).getDate()));
  return v > cierre ? v : new Date(a, m, Math.min(t.dia_vencimiento, new Date(a, m + 1, 0).getDate()));
}
const fechaDe = (d: Date) => d.toISOString().slice(0, 10);

const COLORES = { resumen: "#8fa3c4", cuotas: "#e8762d", prestamos: "#2f5bea", personas: "#d4a017" };

function Barra({ partes }: { partes: { label: string; valor: number; color: string }[] }) {
  const total = partes.reduce((a, p) => a + p.valor, 0);
  const visibles = partes.filter((p) => p.valor > 0);
  if (!total) return null;
  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex h-3 gap-[3px] overflow-hidden rounded-full">
        {visibles.map((p) => <div key={p.label} className="suave h-full rounded-full" style={{ width: `${(p.valor / total) * 100}%`, background: p.color }} />)}
      </div>
      <dl className="flex flex-wrap gap-x-5 gap-y-1.5 text-[13px]">
        {visibles.map((p) => (
          <div key={p.label} className="flex items-center gap-1.5">
            <i className="h-2 w-2 rounded-full" style={{ background: p.color }} />
            <dt className="text-muted">{p.label}</dt>
            <dd className="num font-bold">{pesos(p.valor)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/** Una compra en cuotas, dentro de su tarjeta. */
function FilaCuotas({ p }: { p: PlanCuotas }) {
  const pagadas = p.cuotas_total - p.restantes;
  return (
    <Link href={`/tarjetas/${p.cuenta_id}`} className="press flex w-full flex-col gap-1.5 py-3 pr-4 pl-[68px] text-left hover:bg-surface-2">
      <span className="flex items-baseline gap-3">
        <span className="min-w-0 flex-1 truncate text-[15px] font-semibold">{p.descripcion}</span>
        <span className="num shrink-0 font-bold">{pesos(Number(p.monto_cuota) * p.restantes, p.moneda)}</span>
      </span>
      <span className="text-[13px] text-muted">
        {p.restantes === 1 ? "Última cuota" : `Faltan ${p.restantes} de ${p.cuotas_total}`} · {pesos(Number(p.monto_cuota), p.moneda)}/mes · hasta {mesCorto(p.ultimo_periodo)}
      </span>
      <span className="h-1 overflow-hidden rounded-full bg-surface-2" aria-hidden>
        <span className="block h-full rounded-full bg-[#e8762d]" style={{ width: `${Math.max(2, (pagadas / p.cuotas_total) * 100)}%` }} />
      </span>
    </Link>
  );
}

function GrupoTarjeta({ t }: { t: Tarjeta }) {
  const planes = t.planes.filter((p) => p.restantes > 0);
  const enCuotas = planes.reduce((a, p) => a + Number(p.monto_cuota) * p.restantes, 0);
  const resumen = Math.max(0, Number(t.deuda) - enCuotas);
  return (
    <div className="overflow-hidden rounded-[22px] bg-surface shadow-soft">
      <Link href={`/tarjetas/${t.cuenta_id}`} className="press flex items-center gap-3 px-4 py-3.5 hover:bg-surface-2">
        <IconoCat icono="tarjeta_credito" color="orange" />
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="truncate text-[15px] font-extrabold">{t.nombre}</span>
          <span className="truncate text-[13px] text-muted">
            {t.dia_cierre ? `Cierra el ${t.dia_cierre}${t.dia_vencimiento ? `, vence el ${t.dia_vencimiento}` : ""}` : "Configurá el día de cierre y vencimiento"}
          </span>
        </span>
        <span className="num shrink-0 text-lg font-extrabold">{pesos(Number(t.deuda))}</span>
      </Link>
      {resumen > 0 && (
        <div className="flex items-baseline gap-3 border-t border-line py-3 pr-4 pl-[68px]">
          <span className="min-w-0 flex-1 text-[15px] font-semibold">Compras en un pago</span>
          <span className="num shrink-0 font-bold">{pesos(resumen)}</span>
        </div>
      )}
      {planes.map((p) => <div key={p.id} className="border-t border-line"><FilaCuotas p={p} /></div>)}
    </div>
  );
}

interface Pago { fecha: string; que: string; monto: number; href: string }

/** Lo que vence en los próximos ~35 días: resúmenes de tarjeta y cuotas de préstamos. */
function proximosPagos(tarjetas: Tarjeta[], deudas: Deuda[]): Pago[] {
  const hoy = new Date();
  hoy.setHours(0, 0, 0, 0);
  const limite = new Date(hoy.getTime() + 35 * 86400000);
  const out: Pago[] = [];
  for (const t of tarjetas) {
    if (Number(t.deuda) <= 0) continue;
    const planes = t.planes.filter((p) => p.moneda === "ARS");
    const futuras = planes.reduce((a, p) => {
      const k = Math.max(0, Math.min(p.cuotas_total, distancia(p.primer_periodo, t.proximo_periodo) + 1));
      return a + Number(p.monto_cuota) * (p.cuotas_total - k);
    }, 0);
    // El resumen abierto: lo que no son cuotas futuras (puede incluir uno ya cerrado sin pagar)
    const total = Math.max(0, Number(t.deuda) - futuras);
    const v = vencimiento(t, t.proximo_periodo);
    if (total > 0) out.push({ fecha: fechaDe(v), que: `Resumen ${t.nombre}`, monto: total, href: `/tarjetas/${t.cuenta_id}` });
  }
  for (const d of deudas) {
    if (d.tipo === "prestamo" && d.proximo_vencimiento && d.cuota_sugerida && new Date(d.proximo_vencimiento + "T12:00:00") <= limite)
      out.push({ fecha: d.proximo_vencimiento, que: `Cuota ${d.nombre}`, monto: Number(d.cuota_sugerida), href: "/deudas" });
  }
  return out.sort((a, b) => a.fecha.localeCompare(b.fecha));
}

/** Cuánto pagás por mes en cuotas (tarjetas + préstamos) los próximos 12 meses. */
function Liberacion({ tarjetas, deudas }: { tarjetas: Tarjeta[]; deudas: Deuda[] }) {
  const base = tarjetas[0]?.proximo_periodo ?? (() => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`; })();
  const meses = Array.from({ length: 12 }, (_, k) => {
    const per = sumarPeriodo(base, k);
    let v = 0;
    for (const t of tarjetas) for (const p of t.planes) if (p.moneda === "ARS" && cuotaEn(p, per)) v += Number(p.monto_cuota);
    for (const d of deudas) if (d.tipo === "prestamo" && d.cuota_sugerida && (d.cuotas_restantes ?? 999) > k) v += Number(d.cuota_sugerida);
    return { per, v };
  });
  const max = Math.max(...meses.map((m) => m.v));
  if (!max) return null;
  let mayorBaja: { per: string; baja: number } | null = null;
  for (let i = 1; i < meses.length; i++) {
    const baja = meses[i - 1].v - meses[i].v;
    if (baja > 0 && (!mayorBaja || baja > mayorBaja.baja)) mayorBaja = { per: meses[i].per, baja };
  }
  const fin = meses.findIndex((m) => m.v === 0);
  return (
    <Seccion titulo="Cuándo te liberás">
      <div className="flex flex-col gap-4 rounded-[22px] bg-surface p-5 shadow-soft">
        <p className="text-[15px]">
          Este mes pagás <b className="num whitespace-nowrap">{pesos(meses[0].v)}</b> en cuotas.
          {mayorBaja && <> En <b>{mesCorto(mayorBaja.per)}</b> se te liberan <b className="num whitespace-nowrap">{pesos(mayorBaja.baja)}</b> por mes.</>}
          {fin > 0 && <> Desde <b>{mesCorto(meses[fin].per)}</b> no pagás más cuotas.</>}
        </p>
        <div className="flex h-28 items-end gap-1.5" aria-hidden>
          {meses.map((m, i) => (
            <div key={m.per} className="flex flex-1 flex-col items-center gap-1">
              <div className="w-full rounded-t-md suave" style={{ height: `${Math.max(m.v ? 4 : 0, (m.v / max) * 92)}px`, background: i === 0 ? "var(--accent)" : "var(--line-strong)" }} />
              <span className="text-[10px] font-semibold text-faint">{MESES[Number(m.per.split("-")[1]) - 1].slice(0, 1).toUpperCase()}</span>
            </div>
          ))}
        </div>
      </div>
    </Seccion>
  );
}

export default function DeudasPage() {
  const { data: deudas } = useSWR<Deuda[]>("/deudas");
  const { data: tarjetas } = useSWR<Tarjeta[]>("/tarjetas");
  const [nueva, setNueva] = useState(false);
  const [abierta, setAbierta] = useState<string | null>(null);

  if (!deudas || !tarjetas) return <Esqueleto className="h-96 rounded-[28px]" />;

  const prestamos = deudas.filter((d) => d.tipo === "prestamo");
  const aPersonas = deudas.filter((d) => d.tipo === "debo");
  const meDeben = deudas.filter((d) => d.tipo === "me_deben");
  const ars = (ds: Deuda[]) => ds.filter((d) => d.moneda === "ARS").reduce((a, d) => a + Number(d.saldo), 0);
  const conDeuda = tarjetas.filter((t) => Number(t.deuda) > 0);
  const enCuotas = conDeuda.reduce((a, t) => a + t.planes.filter((p) => p.moneda === "ARS").reduce((b, p) => b + Number(p.monto_cuota) * p.restantes, 0), 0);
  const deTarjetas = conDeuda.reduce((a, t) => a + Number(t.deuda), 0);
  const partes = [
    { label: "Resumen de tarjetas", valor: Math.max(0, deTarjetas - enCuotas), color: COLORES.resumen },
    { label: "Cuotas", valor: enCuotas, color: COLORES.cuotas },
    { label: "Préstamos", valor: ars(prestamos), color: COLORES.prestamos },
    { label: "A personas", valor: ars(aPersonas), color: COLORES.personas },
  ];
  const total = partes.reduce((a, p) => a + p.valor, 0);
  const pagos = proximosPagos(conDeuda, prestamos);
  const vacio = !total && !meDeben.length;

  return (
    <div className="flex flex-col gap-7">
      <Titulo extra={<Boton variante="linea" onClick={() => setNueva(true)}><Plus size={18} /> Nueva</Boton>}>Deudas</Titulo>

      {vacio ? (
        <Vacio titulo="No tenés deudas" accion={<Boton variante="acento" onClick={() => setNueva(true)}><Plus size={18} /> Cargar una</Boton>}>
          Las compras en cuotas con tarjeta aparecen acá solas. También podés cargar préstamos, lo que le debés a alguien o lo que te deben («le presté 20 lucas a juan»).
        </Vacio>
      ) : (
        <>
          <section className="flex flex-col gap-5 rounded-[28px] bg-surface p-6 shadow-soft lg:p-8">
            <div className="flex flex-wrap items-end justify-between gap-x-10 gap-y-3">
              <Total etiqueta="Debés en total" valor={total} />
              {meDeben.length > 0 && <Total etiqueta="Te deben" valor={ars(meDeben)} tono="ok" />}
            </div>
            <Barra partes={partes} />
          </section>

          <div className="grid grid-cols-1 gap-7 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-start lg:gap-x-10">
            <div className="flex min-w-0 flex-col gap-7 lg:col-start-1 lg:row-start-1">
              {pagos.length > 0 && (
                <Seccion titulo="Lo que viene">
                  <Lista>
                    {pagos.map((p) => (
                      <Link key={p.que + p.fecha} href={p.href} className="press flex items-center gap-3 px-4 py-3.5 hover:bg-surface-2">
                        <span className="flex w-12 shrink-0 flex-col items-center rounded-xl bg-surface-2 py-1.5 leading-none">
                          <span className="text-lg font-extrabold">{Number(p.fecha.slice(8, 10))}</span>
                          <span className="text-[11px] font-bold text-muted uppercase">{MESES[Number(p.fecha.slice(5, 7)) - 1].slice(0, 3)}</span>
                        </span>
                        <span className="min-w-0 flex-1 truncate font-bold">{p.que}</span>
                        <span className="num shrink-0 font-extrabold">{pesos(p.monto)}</span>
                      </Link>
                    ))}
                  </Lista>
                  <p className="text-xs text-faint">El resumen incluye las cuotas de ese mes y las compras en un pago.</p>
                </Seccion>
              )}
              <Liberacion tarjetas={conDeuda} deudas={prestamos} />
            </div>

            <div className="flex min-w-0 flex-col gap-7 lg:col-start-2 lg:row-span-2 lg:row-start-1">
              {conDeuda.length > 0 && (
                <Seccion titulo="Tarjetas">
                  {conDeuda.map((t) => <GrupoTarjeta key={t.cuenta_id} t={t} />)}
                </Seccion>
              )}
              {prestamos.length > 0 && (
                <Seccion titulo="Préstamos">
                  <Lista>{prestamos.map((d) => <FilaDeuda key={d.id} d={d} onAbrir={() => setAbierta(d.id)} />)}</Lista>
                </Seccion>
              )}
              {aPersonas.length > 0 && (
                <Seccion titulo="Le debés a">
                  <Lista>{aPersonas.map((d) => <FilaDeuda key={d.id} d={d} onAbrir={() => setAbierta(d.id)} />)}</Lista>
                </Seccion>
              )}
              {meDeben.length > 0 && (
                <Seccion titulo="Te deben">
                  <Lista>{meDeben.map((d) => <FilaDeuda key={d.id} d={d} onAbrir={() => setAbierta(d.id)} />)}</Lista>
                </Seccion>
              )}
            </div>

            <div className="flex min-w-0 flex-col gap-7 lg:col-start-1 lg:row-start-2">
              <Plan tarjetas={tarjetas} />
            </div>
          </div>
        </>
      )}

      <NuevaDeudaSheet abierto={nueva} onCerrar={() => setNueva(false)} />
      <DeudaSheet id={abierta} onCerrar={() => setAbierta(null)} />
    </div>
  );
}
