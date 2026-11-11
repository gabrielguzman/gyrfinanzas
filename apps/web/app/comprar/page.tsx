"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { CalendarClock, ChevronDown, ShoppingBag, Sparkles } from "lucide-react";
import { MedioChips } from "@/components/Selectores";
import { useApp } from "@/components/Shell";
import { Boton, Campo, Chip, Mensaje, Seccion, Titulo, cx, inputCls } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { fechaCorta, hoyISO, MESES, monto } from "@/lib/format";
import { vibrar } from "@/lib/hooks";

interface Mes { desde: string; para_gastar: string | null; cuotas: string }
interface Foto {
  hoy: string | null; por_dia: string | null; manana: string | null; restante: string | null; meses: Mes[];
  rojo: { fecha: string; saldo: string } | null; minimo: { fecha: string; saldo: string }; liquido: string; meses_fondo: string | null;
}
interface Simulacion {
  descripcion: string; monto: string; cuotas: number; medio_pago_id: string | null; medio: string | null; con_tarjeta: boolean;
  antes: Foto; despues: Foto; veredicto: "si" | "cuidado" | "no"; motivos: string[];
  primera_cuota: string | null; mejor_dia: string | null; primera_cuota_mejor_dia: string | null;
  cuotas_contado: { contado: string; total_cuotas: string; cuota: string; cuotas: number; inflacion: string; valor_hoy_cuotas: string; diferencia: string; tasa_mensual: string | null; conviene: string } | null;
}

const num = (s: string) => s.replace(/\./g, "").replace(",", ".").replace(/[^\d.]/g, "");
const miles = (v: string | number | null | undefined) => (v == null || v === "" ? "" : Math.round(Number(v)).toLocaleString("es-AR"));
const pct = (v: string | number) => String(Number(v)).replace(".", ",");
const EJEMPLOS = ["zapatillas 120k debito", "notebook 1.2M en 12 cuotas visa", "aire acondicionado 900k en 6 cuotas"];
const CUOTAS = [1, 3, 6, 12, 18];

const VEREDICTO = {
  si: { titulo: "Sí, tranqui", caja: "bg-ok-soft", texto: "text-ok" },
  cuidado: { titulo: "Con cuidado", caja: "bg-warn-soft", texto: "text-warn-ink" },
  no: { titulo: "Mejor no ahora", caja: "bg-danger-soft", texto: "text-danger" },
};

function Comparacion({ label, antes, despues, formato = (v: number) => monto(v), mejorSiSube = true }: {
  label: string; antes: number | null; despues: number | null; formato?: (v: number) => string; mejorSiSube?: boolean;
}) {
  if (antes == null || despues == null) return null;
  const cambia = Math.round(antes) !== Math.round(despues);
  const peor = mejorSiSube ? despues < antes : despues > antes;
  return (
    <div className="flex flex-col gap-1 rounded-[20px] bg-surface p-4 shadow-soft">
      <span className="text-[13px] font-semibold text-muted">{label}</span>
      <span className={cx("display num text-[26px] leading-none font-bold", cambia && peor && despues < 0 && "text-danger")}>{formato(despues)}</span>
      <span className="num text-xs text-faint">{cambia ? <>antes {formato(antes)}</> : "no cambia"}</span>
    </div>
  );
}

function Meses({ antes, despues }: { antes: Mes[]; despues: Mes[] }) {
  if (!antes.length || antes[0].para_gastar == null) return null;
  const vals = [...antes, ...despues].map((m) => Math.max(0, Number(m.para_gastar ?? 0)));
  const max = Math.max(1, ...vals);
  return (
    <div className="flex flex-col gap-3 rounded-[22px] bg-surface p-5 shadow-soft">
      <div className="flex gap-4 text-xs font-semibold text-muted" aria-hidden>
        <span className="flex items-center gap-1.5"><i className="h-2 w-3 rounded-full bg-line-strong" /> Sin la compra</span>
        <span className="flex items-center gap-1.5"><i className="h-2 w-3 rounded-full bg-accent" /> Con la compra</span>
      </div>
      {antes.map((a, i) => {
        const d = despues[i];
        const va = Number(a.para_gastar ?? 0), vd = Number(d?.para_gastar ?? 0);
        const fecha = new Date(a.desde + "T12:00:00");
        return (
          <div key={a.desde} className="grid grid-cols-[72px_minmax(0,1fr)_auto] items-center gap-3">
            <span className="text-sm font-semibold capitalize">{MESES[fecha.getMonth()].slice(0, 3)}</span>
            <div className="flex flex-col gap-1">
              <div className="h-2 rounded-full bg-line-strong suave" style={{ width: `${Math.max(1, (Math.max(0, va) / max) * 100)}%` }} />
              <div className={cx("h-2 rounded-full suave", vd < 0 ? "bg-danger" : "bg-accent")} style={{ width: `${Math.max(1, (Math.max(0, vd) / max) * 100)}%` }} />
            </div>
            <span className={cx("num w-24 text-right text-sm font-bold", vd < 0 && "text-danger", vd !== va && vd >= 0 && "text-ink")}>{monto(vd)}</span>
          </div>
        );
      })}
      <p className="text-xs text-faint">Lo que te quedaría para gastar en cada mes, después de fijos, cuotas y metas.</p>
    </div>
  );
}

export default function ComprarPage() {
  const router = useRouter();
  const { aviso, refrescar } = useApp();
  const [texto, setTexto] = useState("");
  const [medio, setMedio] = useState<string | null>(null);
  const [cuotas, setCuotas] = useState<number | null>(null);
  const [masDatos, setMasDatos] = useState(false);
  const [contado, setContado] = useState("");
  const [totalCuotas, setTotalCuotas] = useState("");
  const [inflacion, setInflacion] = useState("2");
  const [s, setS] = useState<Simulacion | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const pedido = useRef(0);

  useEffect(() => {
    if (texto.trim().length < 3) {
      setS(null);
      setError(null);
      return;
    }
    const n = ++pedido.current;
    const t = window.setTimeout(async () => {
      setCargando(true);
      try {
        const r = await api.post<Simulacion>("/compra/simular", {
          texto, medio_pago_id: medio, cuotas, precio_contado: num(contado) || null, total_cuotas: num(totalCuotas) || null,
          inflacion: inflacion.replace(",", ".") || "0",
        });
        if (n === pedido.current) { setS(r); setError(null); }
      } catch (e) {
        if (n === pedido.current) { setS(null); setError(e instanceof ApiError ? e.message : "No pude conectar con el servidor"); }
      } finally {
        if (n === pedido.current) setCargando(false);
      }
    }, 450);
    return () => window.clearTimeout(t);
  }, [texto, medio, cuotas, contado, totalCuotas, inflacion]);

  async function loCompre() {
    if (!s) return;
    setGuardando(true);
    try {
      const total = s.cuotas > 1 && s.cuotas_contado ? s.cuotas_contado.total_cuotas : s.monto;
      await api.post("/movimientos", {
        tipo: "gasto", fecha: hoyISO(), monto: total, medio_pago_id: s.medio_pago_id, cuotas: s.cuotas > 1 ? s.cuotas : null,
        descripcion: s.cuotas > 1 ? `${s.descripcion} (${s.cuotas} cuotas)` : s.descripcion,
        estado: s.medio_pago_id ? "confirmado" : "pendiente",
      });
      vibrar();
      refrescar();
      aviso(`Cargado: ${s.descripcion} ${monto(total)}`);
      router.push("/");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No pude conectar con el servidor");
    } finally {
      setGuardando(false);
    }
  }

  const v = s ? VEREDICTO[s.veredicto] : null;
  const c = s?.cuotas_contado;
  const n = (x: string | null | undefined) => (x == null ? null : Number(x));

  return (
    <div className="flex flex-col gap-7">
      <Titulo>¿Me lo puedo comprar?</Titulo>
      <div className="grid grid-cols-1 gap-7 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)] lg:items-start lg:gap-10">
        <div className="flex min-w-0 flex-col gap-4 lg:sticky lg:top-10">
          <div className="flex flex-col gap-4 rounded-[24px] bg-surface p-5 shadow-soft">
            <label className="flex items-center gap-3">
              <ShoppingBag size={22} className="shrink-0 text-accent" aria-hidden />
              <span className="sr-only">Qué querés comprar</span>
              <input
                className="w-full bg-transparent text-xl font-bold outline-none placeholder:font-semibold placeholder:text-faint"
                placeholder="notebook 1.2M en 12 cuotas visa" value={texto} onChange={(e) => setTexto(e.target.value)} autoFocus
              />
            </label>
            {!texto && (
              <div className="flex flex-wrap gap-1.5">
                {EJEMPLOS.map((e) => <Chip key={e} onClick={() => setTexto(e)}>{e}</Chip>)}
              </div>
            )}
            <div className="flex flex-col gap-2">
              <span className="text-[13px] font-bold">Con qué</span>
              <MedioChips valor={medio ?? s?.medio_pago_id ?? null} onCambio={setMedio} />
            </div>
            <div className="flex flex-col gap-2">
              <span className="text-[13px] font-bold">Cuotas</span>
              <div className="flex flex-wrap gap-1.5">
                {CUOTAS.map((k) => (
                  <Chip key={k} activo={(cuotas ?? s?.cuotas ?? 1) === k} onClick={() => setCuotas(k)}>{k === 1 ? "Un pago" : k}</Chip>
                ))}
              </div>
            </div>
            <button onClick={() => setMasDatos((m) => !m)} className="flex w-fit items-center gap-1 text-sm font-bold text-muted" aria-expanded={masDatos}>
              Precio de contado, interés e inflación <ChevronDown size={15} className={cx("transition-transform", masDatos && "rotate-180")} />
            </button>
            {masDatos && (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <Campo label="Contado sale" ayuda="Si hay descuento">
                  <input className={inputCls + " num"} inputMode="numeric" value={contado} onChange={(e) => setContado(miles(num(e.target.value)))} placeholder={s ? miles(s.monto) : ""} />
                </Campo>
                <Campo label="En cuotas, total" ayuda="Si tiene interés">
                  <input className={inputCls + " num"} inputMode="numeric" value={totalCuotas} onChange={(e) => setTotalCuotas(miles(num(e.target.value)))} placeholder={s ? miles(s.monto) : ""} />
                </Campo>
                <Campo label="Inflación mensual %" ayuda="Estimada; septiembre 2026 fue 1,9%">
                  <input className={inputCls + " num"} inputMode="decimal" value={inflacion} onChange={(e) => setInflacion(e.target.value.replace(/[^\d,.]/g, ""))} />
                </Campo>
              </div>
            )}
          </div>
          <p className="text-xs text-faint">Es una simulación: no se guarda nada hasta que toques «Lo compré».</p>
        </div>

        <div className={cx("flex min-w-0 flex-col gap-6 transition-opacity", cargando && "opacity-60")}>
          {error && <Mensaje>{error}</Mensaje>}
          {!s && !error && (
            <div className="flex flex-col items-start gap-3 rounded-[24px] border-2 border-dashed border-line-strong p-6">
              <Sparkles size={24} className="text-accent" />
              <p className="max-w-[46ch] text-sm text-muted">
                Escribilo como cuando cargás un gasto. Te muestro cómo te cambia el día a día, los meses que vienen y el calendario, y si te conviene en cuotas o de contado.
              </p>
            </div>
          )}
          {s && v && (
            <>
              <section className={cx("flex flex-col gap-3 rounded-[24px] p-6", v.caja)}>
                <p className="text-sm font-semibold text-muted">
                  {s.descripcion} · <span className="num">{monto(s.monto)}</span>{s.cuotas > 1 && ` en ${s.cuotas} cuotas`}{s.medio && ` · ${s.medio}`}
                </p>
                <p className={cx("display text-[36px] leading-none font-bold", v.texto)}>{v.titulo}</p>
                <ul className="flex flex-col gap-1.5 text-[15px]">
                  {s.motivos.map((m) => <li key={m}>{m}</li>)}
                </ul>
              </section>

              <div className="grid grid-cols-2 gap-3">
                <Comparacion label="Hoy podés gastar" antes={n(s.antes.hoy)} despues={n(s.despues.hoy)} />
                <Comparacion label="Por día desde mañana" antes={n(s.antes.manana)} despues={n(s.despues.manana)} />
                <Comparacion label="Lo más bajo de tus cuentas (90 días)" antes={n(s.antes.minimo.saldo)} despues={n(s.despues.minimo.saldo)} />
                <Comparacion
                  label="Fondo de emergencia" antes={n(s.antes.meses_fondo)} despues={n(s.despues.meses_fondo)}
                  formato={(x) => (x <= 0 ? "Sin fondo" : `${pct(x.toFixed(1))} meses`)}
                />
              </div>

              {s.con_tarjeta && s.primera_cuota && (
                <div className="flex gap-3 rounded-[22px] bg-surface p-4 text-sm shadow-soft">
                  <CalendarClock size={20} className="mt-0.5 shrink-0 text-accent" />
                  <p>
                    {s.cuotas > 1 ? "La primera cuota" : "Lo pagás"} con el resumen que vence el <b>{fechaCorta(s.primera_cuota)}</b>.
                    {s.mejor_dia && s.primera_cuota_mejor_dia && (
                      <> Si esperás al <b>{fechaCorta(s.mejor_dia)}</b> (después del cierre), {s.cuotas > 1 ? "la primera cuota se paga" : "lo pagás"} el <b>{fechaCorta(s.primera_cuota_mejor_dia)}</b>: un mes más de aire.</>
                    )}
                  </p>
                </div>
              )}

              {s.despues.meses.length > 0 && s.despues.meses[0].para_gastar != null && (
                <Seccion titulo="Los próximos meses">
                  <Meses antes={s.antes.meses} despues={s.despues.meses} />
                </Seccion>
              )}

              {c && (
                <Seccion titulo="¿Cuotas o contado?">
                  <div className="flex flex-col gap-2 rounded-[22px] bg-surface p-5 text-[15px] shadow-soft">
                    <p className="display text-[22px] font-bold">
                      {c.conviene === "cuotas" ? "Conviene en cuotas" : c.conviene === "contado" ? "Conviene de contado" : "Da casi lo mismo"}
                    </p>
                    <p className="text-muted">
                      {c.cuotas} cuotas de <b className="num text-ink">{monto(Math.round(Number(c.cuota)))}</b>, con {pct(c.inflacion)}% de inflación por mes, valen{" "}
                      <b className="num text-ink">{monto(c.valor_hoy_cuotas)}</b> en plata de hoy, contra <b className="num text-ink">{monto(c.contado)}</b> de contado
                      {Number(c.diferencia) > 0 ? <>: ahorrás <b className="num text-ok">{monto(c.diferencia)}</b>.</> : Number(c.diferencia) < 0 ? <>: pagás <b className="num text-danger">{monto(-Number(c.diferencia))}</b> de más.</> : "."}
                    </p>
                    {c.tasa_mensual && Number(c.tasa_mensual) > 0 && (
                      <p className="text-sm text-muted">
                        Las cuotas tienen un interés de {pct(c.tasa_mensual)}% por mes sobre el contado
                        {Number(c.tasa_mensual) > Number(c.inflacion) ? ", más que la inflación." : ", menos que la inflación."}
                      </p>
                    )}
                    {c.conviene === "cuotas" && <p className="text-xs text-faint">Siempre que la plata que no gastás hoy quede rindiendo o al menos no se te vaya en otra cosa.</p>}
                  </div>
                </Seccion>
              )}

              <div className="flex gap-2">
                <Boton variante={s.veredicto === "no" ? "linea" : "acento"} className="flex-1" disabled={guardando} onClick={loCompre}>
                  Lo compré: cargarlo
                </Boton>
                <Boton variante="linea" onClick={() => { setTexto(""); setCuotas(null); setMedio(null); }}>Otra</Boton>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
