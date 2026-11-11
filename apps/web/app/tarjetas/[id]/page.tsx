"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useRef, useState } from "react";
import useSWR from "swr";
import { ArrowLeft, CalendarCheck, FileUp, Plus, TrendingDown, X } from "lucide-react";
import { TransferenciaSheet } from "@/components/CuentaForms";
import { Sheet } from "@/components/Sheet";
import { useApp } from "@/components/Shell";
import { Boton, Campo, Esqueleto, Lista, Mensaje, Seccion, Vacio, cx, inputCls } from "@/components/ui";
import { api, ApiError, type Plan, type ResumenTarjeta, type Tarjeta } from "@/lib/api";
import { fechaCorta, monto, nombrePeriodo } from "@/lib/format";
import { useContador } from "@/lib/hooks";

/** «Lo que compres desde el 27 nov entra en el resumen de diciembre y se paga en enero». */
function explicarMejorDia(t: Tarjeta): string {
  const d = new Date(t.mejor_dia_compra + "T12:00:00");
  const siguiente = (a: number, m: number) => (m === 12 ? [a + 1, 1] : [a, m + 1]);
  // Después del cierre, la compra entra en el resumen del mes siguiente.
  let [a, m] = [d.getFullYear(), d.getMonth() + 1];
  if (d.getDate() > (t.dia_cierre ?? 25)) [a, m] = siguiente(a, m);
  const [pa, pm] = siguiente(a, m);
  const fmt = (x: number, y: number) => `${x}-${String(y).padStart(2, "0")}`;
  const resumen = fmt(a, m);
  const pago = fmt(pa, pm);
  const dia = t.dia_vencimiento ? `el ${t.dia_vencimiento} de ` : "en ";
  return `Recién cerrado el resumen: lo que compres ese día entra en el de ${nombrePeriodo(resumen)} y lo pagás ${dia}${nombrePeriodo(pago)}.`;
}

function SubirResumen({ tarjeta, variante = "claro" }: { tarjeta: Tarjeta; variante?: "claro" | "oscuro" }) {
  const ref = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const { aviso } = useApp();
  const [subiendo, setSubiendo] = useState(false);
  return (
    <>
      <input
        ref={ref}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={async (e) => {
          const f = e.target.files?.[0];
          e.target.value = "";
          if (!f) return;
          setSubiendo(true);
          try {
            const r = await api.subir<ResumenTarjeta>(`/tarjetas/${tarjeta.cuenta_id}/resumenes`, f);
            router.push(`/tarjetas/${tarjeta.cuenta_id}/resumen/${r.id}`);
          } catch (err) {
            aviso(err instanceof ApiError ? err.message : "No pude subir el PDF");
            setSubiendo(false);
          }
        }}
      />
      <button
        onClick={() => ref.current?.click()}
        disabled={subiendo}
        className={cx(
          "press flex min-h-12 flex-1 items-center justify-center gap-2 rounded-2xl px-4 text-sm font-bold disabled:opacity-60",
          variante === "oscuro" ? "bg-white text-[#17233d]" : "bg-ink text-ground"
        )}
      >
        <FileUp size={18} /> {subiendo ? "Subiendo…" : "Subir resumen PDF"}
      </button>
    </>
  );
}

function Cabecera({ t, onPagar }: { t: Tarjeta; onPagar: () => void }) {
  const r = t.ultimo_resumen;
  const total = Number(r?.total_ars ?? t.deuda);
  const animado = useContador(total);
  return (
    <section className="relative flex flex-col gap-5 overflow-hidden rounded-[28px] bg-slab p-6 text-slab-ink shadow-soft lg:p-8">
      <div className="flex items-center justify-between gap-3 text-[13px] text-slab-muted">
        <span>{r ? `Resumen de ${nombrePeriodo(r.periodo ?? t.proximo_periodo)}` : "Sin resúmenes cargados"}</span>
        {r?.fecha_vencimiento && <span>Vence el {fechaCorta(r.fecha_vencimiento)}</span>}
      </div>
      <div>
        <p className="text-sm text-slab-muted">{r ? "Total a pagar" : "Lo que debés hoy"}</p>
        <p className="display num text-[clamp(40px,11vw,56px)] leading-[0.95] font-bold">{monto(animado === total ? total : Math.round(animado))}</p>
        {r?.total_usd && Number(r.total_usd) > 0 && <p className="mt-1 text-sm text-slab-muted">y {monto(r.total_usd, "USD")}</p>}
      </div>
      {r?.pago_minimo && (
        <div className="grid grid-cols-2 gap-2.5">
          <div className="rounded-2xl bg-white/8 p-3">
            <p className="text-xs text-slab-muted">Pago mínimo</p>
            <p className="num text-base font-bold">{monto(r.pago_minimo)}</p>
          </div>
          <div className="rounded-2xl bg-[#ffab73]/15 p-3">
            <p className="text-xs text-[#ffcfae]">Si pagás el mínimo</p>
            <p className="num text-base font-bold text-[#ffcfae]">
              {r.interes_si_minimo ? `+${monto(r.interes_si_minimo)} de interés` : "pagás intereses"}
            </p>
          </div>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        <SubirResumen tarjeta={t} variante="oscuro" />
        {Number(t.deuda) > 0 && (
          <button onClick={onPagar} className="press min-h-12 rounded-2xl bg-white/12 px-5 text-sm font-bold">
            Pagar
          </button>
        )}
      </div>
    </section>
  );
}

function Compromisos({ t }: { t: Tarjeta }) {
  const max = Math.max(1, ...t.compromisos.map((c) => Number(c.total)));
  const [activo, setActivo] = useState<number | null>(null);
  if (!t.compromisos.some((c) => Number(c.total) > 0)) return null;
  return (
    <Seccion titulo="Cuotas que vienen" extra={<span className="text-[13px] font-semibold text-muted">por resumen</span>}>
      <div className="rounded-[22px] bg-surface p-5 shadow-soft">
        <div className="grid h-40 grid-cols-6 items-end gap-2.5" role="list" aria-label="Cuotas comprometidas por mes">
          {t.compromisos.map((c, i) => {
            const v = Number(c.total);
            return (
              <button
                key={c.periodo}
                role="listitem"
                onPointerEnter={() => setActivo(i)}
                onPointerLeave={() => setActivo(null)}
                onFocus={() => setActivo(i)}
                onBlur={() => setActivo(null)}
                aria-label={`${nombrePeriodo(c.periodo)}: ${monto(v)} en ${c.planes} ${c.planes === 1 ? "plan" : "planes"}`}
                className="flex h-full flex-col items-center justify-end gap-1.5"
              >
                <span className="flex w-full flex-1 flex-col items-center justify-end gap-1">
                <span className={cx("num text-[11px] font-bold", activo === i ? "text-ink" : "text-muted")}>
                  {v ? `${Math.round(v / 1000)}k` : "—"}
                </span>
                <span
                  className="suave w-full rounded-t-[8px] rounded-b-[3px]"
                  style={{
                    height: `${Math.max(3, (v / max) * 82)}%`,
                    background: i === 0 ? "var(--warn)" : "color-mix(in oklab, var(--warn) 38%, var(--surface-2))",
                    outline: activo === i ? "2px solid var(--ink)" : "none",
                    outlineOffset: 2,
                  }}
                />
                </span>
                <span className="text-xs font-semibold text-muted">{nombrePeriodo(c.periodo, true)}</span>
              </button>
            );
          })}
        </div>
        <p className="mt-4 text-[13px] text-muted">
          {activo != null
            ? `${nombrePeriodo(t.compromisos[activo].periodo)}: ${monto(t.compromisos[activo].total)} de ${t.compromisos[activo].planes} ${t.compromisos[activo].planes === 1 ? "plan" : "planes"}.`
            : `El próximo resumen (${nombrePeriodo(t.compromisos[0].periodo)}) ya trae ${monto(t.compromisos[0].total)} en cuotas.`}
        </p>
      </div>
    </Seccion>
  );
}

function FilaPlan({ p, onQuitar }: { p: Plan; onQuitar: () => void }) {
  const hechas = p.cuotas_total - p.restantes;
  return (
    <div className="flex flex-col gap-2.5 px-4 py-3.5">
      <div className="flex items-baseline justify-between gap-3">
        <span className="truncate font-bold">{p.descripcion}</span>
        <span className="num shrink-0 font-extrabold">{monto(p.monto_cuota, p.moneda)}<span className="text-xs font-semibold text-muted">/mes</span></span>
      </div>
      <div className="flex h-2 gap-[2px]" aria-hidden>
        {Array.from({ length: p.cuotas_total }, (_, i) => (
          <span
            key={i}
            className="flex-1 rounded-full"
            style={{ background: i < hechas ? "var(--accent)" : i === hechas ? "color-mix(in oklab, var(--accent) 45%, var(--surface-2))" : "var(--surface-2)" }}
          />
        ))}
      </div>
      <div className="flex items-center justify-between gap-2 text-[13px] text-muted">
        <span>
          {p.cuota_actual ? `Viene la cuota ${p.cuota_actual} de ${p.cuotas_total}` : `${p.cuotas_total} cuotas`}
          {" · "}termina en {nombrePeriodo(p.ultimo_periodo)}
        </span>
        <button onClick={onQuitar} aria-label={`Quitar plan ${p.descripcion}`} className="press flex h-9 w-9 items-center justify-center rounded-xl text-faint hover:text-ink">
          <X size={16} />
        </button>
      </div>
    </div>
  );
}

function NuevoPlanSheet({ abierto, onCerrar, tarjeta }: { abierto: boolean; onCerrar: () => void; tarjeta: Tarjeta }) {
  const { aviso, refrescar } = useApp();
  const [desc, setDesc] = useState("");
  const [cuota, setCuota] = useState("");
  const [total, setTotal] = useState("12");
  const [actual, setActual] = useState("1");
  const [error, setError] = useState<string | null>(null);
  const ok = desc.trim() && Number(cuota.replace(/\./g, "").replace(",", ".")) > 0 && Number(total) >= 2 && Number(actual) >= 1;
  return (
    <Sheet abierto={abierto} onCerrar={onCerrar} titulo="Cuotas que ya venías pagando">
      <p className="-mt-2 text-sm text-muted">Para compras anteriores a la app. Las nuevas en cuotas se agregan solas cuando las cargás.</p>
      <Campo label="Qué compraste"><input className={inputCls} value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Heladera" /></Campo>
      <Campo label="Monto de cada cuota"><input className={inputCls + " num"} inputMode="decimal" value={cuota} onChange={(e) => setCuota(e.target.value)} placeholder="38.900" /></Campo>
      <div className="grid grid-cols-2 gap-3">
        <Campo label="Cuotas en total"><input className={inputCls} inputMode="numeric" value={total} onChange={(e) => setTotal(e.target.value)} /></Campo>
        <Campo label={`Cuota que viene en ${nombrePeriodo(tarjeta.proximo_periodo)}`}><input className={inputCls} inputMode="numeric" value={actual} onChange={(e) => setActual(e.target.value)} /></Campo>
      </div>
      {error && <Mensaje>{error}</Mensaje>}
      <Boton
        variante="acento"
        disabled={!ok}
        onClick={async () => {
          try {
            await api.post(`/tarjetas/${tarjeta.cuenta_id}/planes`, {
              descripcion: desc.trim(), monto_cuota: cuota.replace(/\./g, "").replace(",", "."),
              cuotas_total: Number(total), cuota_actual: Number(actual),
            });
            refrescar();
            aviso("Plan agregado");
            setDesc(""); setCuota("");
            onCerrar();
          } catch (e) {
            setError(e instanceof ApiError ? e.message : "No pude conectar con el servidor");
          }
        }}
      >
        Agregar plan
      </Boton>
    </Sheet>
  );
}

export default function TarjetaPage() {
  const { id } = useParams<{ id: string }>();
  const { aviso, refrescar } = useApp();
  const { data: t, error, mutate } = useSWR<Tarjeta>(`/tarjetas/${id}`);
  const [pagar, setPagar] = useState(false);
  const [nuevoPlan, setNuevoPlan] = useState(false);
  const [ocultos, setOcultos] = useState<string[]>([]);

  if (error) return <Vacio titulo="No encontré esa tarjeta"><Link href="/cuentas" className="font-bold text-accent">Volver a Cuentas</Link></Vacio>;

  function quitar(p: Plan) {
    setOcultos((o) => [...o, p.id]);
    const timer = window.setTimeout(async () => {
      await api.del(`/planes/${p.id}`).catch(() => {});
      mutate();
      refrescar();
    }, 5000);
    aviso(`Quitado: ${p.descripcion}`, { deshacer: () => { window.clearTimeout(timer); setOcultos((o) => o.filter((x) => x !== p.id)); } });
  }

  return (
    <div className="flex flex-col gap-7">
      <div className="flex items-center gap-3">
        <Link href="/cuentas" aria-label="Volver a Cuentas" className="press flex h-11 w-11 items-center justify-center rounded-full bg-surface shadow-soft">
          <ArrowLeft size={20} />
        </Link>
        <h1 className="display truncate text-[30px] leading-none font-bold">{t?.nombre ?? "Tarjeta"}</h1>
      </div>

      {!t ? (
        <Esqueleto className="h-72 rounded-[28px]" />
      ) : (
        <div className="grid grid-cols-1 gap-7 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:items-start lg:gap-10">
          <div className="flex min-w-0 flex-col gap-5">
            {t.pendiente_revision && (
              <Link href={`/tarjetas/${t.cuenta_id}/resumen/${t.pendiente_revision}`} className="press flex items-center justify-between gap-3 rounded-[20px] bg-accent-soft p-4 font-semibold">
                Tenés un resumen sin terminar de revisar <span className="font-bold text-accent">Seguir</span>
              </Link>
            )}
            <Cabecera t={t} onPagar={() => setPagar(true)} />
            <div className="flex items-center gap-3 rounded-[20px] bg-surface p-4 shadow-soft">
              <CalendarCheck size={22} className="shrink-0 text-accent" />
              <p className="text-sm">
                <b>Mejor día para comprar: {fechaCorta(t.mejor_dia_compra)}.</b>{" "}
                <span className="text-muted">{explicarMejorDia(t)}</span>
              </p>
            </div>
            {!t.dia_cierre && (
              <Mensaje>No cargaste el día de cierre de esta tarjeta: uso el 25. Lo podés corregir subiendo un resumen.</Mensaje>
            )}
            {t.liberacion && (
              <div className="flex items-center gap-3 rounded-[20px] bg-ok-soft p-4">
                <TrendingDown size={22} className="shrink-0 text-ok" />
                <p className="text-sm">
                  <b>En {nombrePeriodo(t.liberacion.periodo)} se te liberan {monto(t.liberacion.monto)} por mes</b>
                  {t.liberacion.planes_que_terminan > 0 && ` porque terminan ${t.liberacion.planes_que_terminan} ${t.liberacion.planes_que_terminan === 1 ? "plan" : "planes"}`}.
                </p>
              </div>
            )}
          </div>

          <div className="flex min-w-0 flex-col gap-7">
            <Compromisos t={t} />
            <Seccion
              titulo="Planes de cuotas"
              extra={<button onClick={() => setNuevoPlan(true)} className="press flex items-center gap-1 text-sm font-bold text-accent"><Plus size={16} /> Agregar</button>}
            >
              {t.planes.filter((p) => !ocultos.includes(p.id)).length ? (
                <Lista>
                  {t.planes.filter((p) => !ocultos.includes(p.id)).map((p) => <FilaPlan key={p.id} p={p} onQuitar={() => quitar(p)} />)}
                </Lista>
              ) : (
                <Vacio titulo="No hay cuotas activas">
                  Cuando cargues algo como «heladera 466k 12 cuotas visa» o subas un resumen, los planes aparecen acá.
                </Vacio>
              )}
            </Seccion>
          </div>
        </div>
      )}

      {t && <TransferenciaSheet key={t.cuenta_id} abierto={pagar} destinoInicial={t.cuenta_id} onCerrar={() => setPagar(false)} />}
      {t && <NuevoPlanSheet abierto={nuevoPlan} onCerrar={() => setNuevoPlan(false)} tarjeta={t} />}
    </div>
  );
}
