"use client";

import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import { Banknote, ChevronDown, CreditCard, HandCoins, Repeat, TriangleAlert } from "lucide-react";
import { SaldoProyectadoChart } from "@/components/Graficos";
import { BarrasCiclo, fraseCiclo } from "@/components/Plan";
import { useApp } from "@/components/Shell";
import { Boton, Campo, Esqueleto, Mensaje, Seccion, Titulo, cx, inputCls } from "@/components/ui";
import { api, ApiError, type CalendarioPlan, type EventoPlan, type Presupuesto } from "@/lib/api";
import { fechaCorta, monto } from "@/lib/format";
import { useContador, vibrar } from "@/lib/hooks";

const num = (s: string) => s.replace(/\./g, "").replace(",", ".").replace(/[^\d.]/g, "");
const miles = (v: string | number | null | undefined) => (v == null || v === "" ? "" : Math.round(Number(v)).toLocaleString("es-AR"));

const ICONO_EVENTO: Record<EventoPlan["tipo"], typeof Banknote> = {
  cobro: Banknote,
  tarjeta: CreditCard,
  prestamo: HandCoins,
  fijo: Repeat,
};

function Linea({ label, valor, signo, fuerte, children }: { label: string; valor: string | number; signo?: "+" | "-"; fuerte?: boolean; children?: React.ReactNode }) {
  const [abierto, setAbierto] = useState(false);
  const fila = (
    <span className={cx("flex items-center justify-between gap-3 py-2.5", fuerte && "font-extrabold")}>
      <span className="flex items-center gap-1.5 text-sm">
        {label}
        {children && <ChevronDown size={15} className={cx("text-faint transition-transform", abierto && "rotate-180")} />}
      </span>
      <span className={cx("num text-[15px]", fuerte ? "font-extrabold" : "font-bold", signo === "-" && !fuerte && "text-muted")}>
        {monto(Math.abs(Number(valor)), "ARS", signo)}
      </span>
    </span>
  );
  if (!children) return fila;
  return (
    <div>
      <button className="w-full text-left" onClick={() => setAbierto((a) => !a)} aria-expanded={abierto}>{fila}</button>
      {abierto && <div className="mb-2 flex flex-col gap-1 rounded-xl bg-surface-2 p-3 text-[13px]">{children}</div>}
    </div>
  );
}

function Ajustes({ p, onGuardado }: { p: Presupuesto; onGuardado: (p: Presupuesto) => void }) {
  const { aviso, refrescar } = useApp();
  const [dia, setDia] = useState(String(p.dia_cobro ?? ""));
  const [ingreso, setIngreso] = useState(miles(p.ingreso_esperado));
  const [ahorro, setAhorro] = useState(Number(p.ahorro) ? miles(p.ahorro) : "");
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  useEffect(() => {
    setDia(String(p.dia_cobro ?? ""));
    setIngreso(miles(p.ingreso_esperado));
    setAhorro(Number(p.ahorro) ? miles(p.ahorro) : "");
  }, [p.dia_cobro, p.ingreso_esperado, p.ahorro]);

  async function guardar() {
    setOcupado(true);
    setError(null);
    try {
      const r = await api.put<Presupuesto>("/plan/ajustes", {
        dia_cobro: dia ? Number(dia) : null,
        ingreso_mensual: num(ingreso) || null,
        ahorro_mensual: num(ahorro) || null,
      });
      vibrar();
      onGuardado(r);
      refrescar();
      aviso("Listo, recalculado");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No pude conectar con el servidor");
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className="flex flex-col gap-4 rounded-[22px] bg-surface p-5 shadow-soft">
      {p.cobro_detectado && (
        <p className="text-sm text-muted">Lo saqué de tu último sueldo cargado. Si no es así, corregilo.</p>
      )}
      <div className="grid grid-cols-[96px_minmax(0,1fr)] gap-3">
        <Campo label="Cobrás el día">
          <input className={inputCls + " num"} inputMode="numeric" value={dia} placeholder="1" onChange={(e) => setDia(e.target.value.replace(/\D/g, "").slice(0, 2))} />
        </Campo>
        <Campo label="Cuánto cobrás por mes">
          <input className={inputCls + " num"} inputMode="numeric" value={ingreso} placeholder="1.200.000" onChange={(e) => setIngreso(miles(num(e.target.value)))} />
        </Campo>
      </div>
      <Campo label="Ahorro extra por mes (además de tus metas)" ayuda="Se aparta antes de calcular lo que podés gastar. Para ahorrar con un objetivo, creá una meta.">
        <input className={inputCls + " num"} inputMode="numeric" value={ahorro} placeholder="0" onChange={(e) => setAhorro(miles(num(e.target.value)))} />
      </Campo>
      {error && <Mensaje>{error}</Mensaje>}
      <Boton variante="primario" disabled={ocupado || !dia || !num(ingreso)} onClick={guardar}>Guardar</Boton>
    </div>
  );
}

function Calendario({ c }: { c: CalendarioPlan }) {
  const [todos, setTodos] = useState(false);
  const serie = useMemo(() => c.serie.map((p) => ({ fecha: p.fecha, saldo: Number(p.saldo) })), [c]);
  const eventos = useMemo(() => c.eventos.map((e) => ({ ...e, monto: Number(e.monto) })), [c]);
  const saldoDe = new Map(c.serie.map((p) => [p.fecha, Number(p.saldo)]));
  const lista = todos ? c.eventos : c.eventos.slice(0, 8);

  return (
    <div className="flex flex-col gap-4">
      {c.rojo ? (
        <div className="flex gap-3 rounded-[20px] bg-danger-soft p-4 text-sm">
          <TriangleAlert size={20} className="mt-0.5 shrink-0 text-danger" />
          <p>
            <b>El {fechaCorta(c.rojo.fecha)} tus cuentas quedarían en {monto(c.rojo.saldo)}.</b>{" "}
            <span className="text-muted">Mirá qué vence ese día: podés mover un pago, usar otra cuenta o gastar menos hasta entonces.</span>
          </p>
        </div>
      ) : (
        <p className="text-sm text-muted">
          Lo más bajo que llegarían tus cuentas es <b className="num text-ink">{monto(c.minimo.saldo)}</b>, el {fechaCorta(c.minimo.fecha)}.
        </p>
      )}
      <div className="rounded-[22px] bg-surface p-5 shadow-soft">
        <SaldoProyectadoChart serie={serie} eventos={eventos} />
        <p className="mt-3 text-xs text-faint">
          Hoy tenés {monto(c.saldo_hoy)} en cuentas en pesos. Supone que gastás {monto(c.gasto_diario)} por día en lo de todos los días.
        </p>
      </div>
      <div className="overflow-hidden rounded-[22px] bg-surface shadow-soft">
        {lista.map((e, i) => {
          const Icono = ICONO_EVENTO[e.tipo];
          const entra = Number(e.monto) > 0;
          const saldo = saldoDe.get(e.fecha);
          return (
            <div key={i} className={cx("flex items-center gap-3 px-4 py-3", i > 0 && "border-t border-line")}>
              <span className={cx("flex h-9 w-9 shrink-0 items-center justify-center rounded-xl", entra ? "bg-ok-soft text-ok" : "bg-surface-2 text-muted")}>
                <Icono size={17} />
              </span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-sm font-bold">{e.titulo}</span>
                <span className="text-xs text-muted">
                  {fechaCorta(e.fecha)}
                  {e.estimado && " · aprox."}
                  {saldo != null && saldo < 0 && <b className="text-danger"> · quedás en {monto(saldo)}</b>}
                </span>
              </span>
              <span className={cx("num shrink-0 font-extrabold", entra && "text-ok")}>{monto(Math.abs(Number(e.monto)), "ARS", entra ? "+" : "-")}</span>
            </div>
          );
        })}
        {c.eventos.length > 8 && (
          <button onClick={() => setTodos((t) => !t)} className="press w-full border-t border-line px-4 py-3 text-sm font-bold text-accent">
            {todos ? "Ver menos" : `Ver los ${c.eventos.length}`}
          </button>
        )}
      </div>
    </div>
  );
}

export default function PlanPage() {
  const { data: p, mutate } = useSWR<Presupuesto>("/plan");
  const { data: cal, mutate: mutarCal } = useSWR<CalendarioPlan>("/plan/calendario");
  const hoy = Number(p?.hoy ?? 0);
  const animado = useContador(Math.abs(hoy));

  if (!p) return <Esqueleto className="h-96 rounded-[28px]" />;
  const pasado = hoy < 0;
  const para = Number(p.para_gastar);
  const proy = p.proyeccion_fin ? Number(p.proyeccion_fin) : null;

  return (
    <div className="flex flex-col gap-7">
      <Titulo>Hasta el cobro</Titulo>
      <div className="grid grid-cols-1 gap-7 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] lg:items-start lg:gap-10">
        <div className="flex min-w-0 flex-col gap-7">
          {p.configurado ? (
            <section className="flex flex-col gap-5 rounded-[28px] bg-slab p-6 text-slab-ink shadow-soft lg:p-8">
              <div>
                <p className="text-sm text-slab-muted">{pasado ? "Hoy te pasaste" : "Hoy podés gastar"}</p>
                <p className={cx("display num text-[clamp(48px,13vw,64px)] leading-[0.95] font-bold", pasado && "text-[#ffab73]")}>{monto(Math.round(animado))}</p>
                <p className="mt-2 text-sm text-slab-muted">{fraseCiclo(p)}.</p>
              </div>
              <dl className="grid grid-cols-3 gap-3 text-[13px]">
                <div>
                  <dt className="text-slab-muted">Por día</dt>
                  <dd className="num text-base font-bold">{monto(Math.max(0, Number(p.por_dia)))}</dd>
                </div>
                <div>
                  <dt className="text-slab-muted">Hoy gastaste</dt>
                  <dd className="num text-base font-bold">{monto(p.gastado_hoy)}</dd>
                </div>
                <div>
                  <dt className="text-slab-muted">Mañana</dt>
                  <dd className="num text-base font-bold">{p.manana ? monto(Math.max(0, Number(p.manana))) : "cobrás"}</dd>
                </div>
              </dl>
              <BarrasCiclo p={p} oscuro />
              {proy != null && para > 0 && proy > para * 1.05 && (
                <p className="rounded-2xl bg-white/8 p-3 text-sm">
                  A este ritmo gastarías <b className="num">{monto(proy)}</b> en el mes: {monto(proy - para)} más de lo que da.
                </p>
              )}
            </section>
          ) : (
            <section className="flex flex-col gap-2 rounded-[28px] bg-slab p-6 text-slab-ink shadow-soft lg:p-8">
              <p className="display text-[30px] leading-tight font-bold">¿Cuánto podés gastar hoy?</p>
              <p className="text-sm text-slab-muted">
                Con cuándo cobrás y cuánto, te digo cada día cuánto podés gastar sin llegar justo a fin de mes. Ya descuento tus gastos fijos, las cuotas y lo que quieras ahorrar.
              </p>
            </section>
          )}

          {p.configurado && (
            <Seccion titulo="De dónde sale">
              <div className="flex flex-col rounded-[22px] bg-surface px-5 py-2 shadow-soft [&>*+*]:border-t [&>*+*]:border-line">
                <Linea label="Cobrás" valor={p.ingreso} signo="+" />
                {Number(p.fijos) > 0 && (
                  <Linea label="Gastos fijos" valor={p.fijos} signo="-">
                    {p.detalle_fijos.map((f) => <span key={f.nombre} className="flex justify-between"><span>{f.nombre}</span><span className="num font-semibold">{monto(f.monto)}</span></span>)}
                  </Linea>
                )}
                {Number(p.cuotas_tarjetas) + Number(p.cuotas_prestamos) > 0 && (
                  <Linea label="Cuotas" valor={Number(p.cuotas_tarjetas) + Number(p.cuotas_prestamos)} signo="-">
                    {p.detalle_cuotas.map((f) => <span key={f.nombre} className="flex justify-between"><span>{f.nombre}</span><span className="num font-semibold">{monto(f.monto)}</span></span>)}
                  </Linea>
                )}
                {Number(p.metas) > 0 && (
                  <Linea label="Metas de ahorro" valor={p.metas} signo="-">
                    {p.detalle_metas.map((f) => <span key={f.nombre} className="flex justify-between"><span>{f.nombre}</span><span className="num font-semibold">{monto(f.monto)}</span></span>)}
                  </Linea>
                )}
                {Number(p.ahorro) > 0 && <Linea label="Ahorro extra" valor={p.ahorro} signo="-" />}
                <Linea label="Para gastar en el mes" valor={p.para_gastar} fuerte />
                <Linea label="Ya gastaste" valor={p.gastado} signo="-" />
                <Linea label={Number(p.restante) >= 0 ? "Te queda" : "Te pasaste"} valor={p.restante} fuerte />
              </div>
              <p className="text-xs text-faint">
                Las compras en cuotas cuentan por cuota, cuando pagás el resumen. Lo que está en la bandeja ya cuenta como gastado.
              </p>
            </Seccion>
          )}

          <Seccion titulo={p.configurado ? "Ajustes" : "Contame"}>
            <Ajustes p={p} onGuardado={(r) => { mutate(r, { revalidate: false }); mutarCal(); }} />
          </Seccion>
        </div>

        <div className="flex min-w-0 flex-col gap-7">
          <Seccion titulo="Próximos 60 días">
            {cal ? <Calendario c={cal} /> : <Esqueleto className="h-80 rounded-[22px]" />}
          </Seccion>
        </div>
      </div>
    </div>
  );
}
