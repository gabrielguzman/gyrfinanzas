"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { CalendarRange, CloudOff, CreditCard, HandCoins, Hash, Paperclip, Plus, Sparkles, TrendingDown } from "lucide-react";
import { HallazgoFila } from "@/components/Hallazgos";
import { BandejaItem } from "@/components/BandejaItem";
import { CategoriasBarras, RitmoChart } from "@/components/Graficos";
import { MovimientoFila } from "@/components/MovimientoFila";
import { HoyCard } from "@/components/Plan";
import { Anillo } from "@/components/Metas";
import { BotonDiscreto, SelectorTema, useApp } from "@/components/Shell";
import { RachaCard } from "@/components/Racha";
import { Boton, Esqueleto, Lista, Seccion, Vacio } from "@/components/ui";
import { api, type Etiquetas } from "@/lib/api";
import type { CalendarioPlan, Meta, Cuenta, Deuda, Hallazgo, Inicio, Movimiento, Presupuesto, Resumen, Tarjeta } from "@/lib/api";
import { cantidadEnCola } from "@/lib/cola";
import { fechaCorta, MESES, monto, nombrePeriodo } from "@/lib/format";
import { useContador } from "@/lib/hooks";

function Disponible({ inicio }: { inicio: Inicio }) {
  const ars = inicio.totales.find((t) => t.moneda === "ARS");
  const usd = inicio.totales.find((t) => t.moneda === "USD");
  const disponible = Number(ars?.disponible ?? 0);
  const enCuentas = Number(ars?.en_cuentas ?? 0);
  const deuda = Number(ars?.deuda_tarjetas ?? 0);
  const futuras = Number(ars?.cuotas_futuras ?? 0);
  const animado = useContador(disponible);
  const pctLibre = enCuentas > 0 ? Math.max(0, Math.min(100, ((enCuentas - deuda) / enCuentas) * 100)) : 0;

  return (
    <section className="relative overflow-hidden rounded-[28px] bg-slab p-6 text-slab-ink shadow-soft lg:p-8" aria-label="Disponible real">
      <svg className="pointer-events-none absolute -top-16 -right-16 h-64 w-64 opacity-[0.12]" viewBox="0 0 200 200" aria-hidden>
        <circle cx="100" cy="100" r="70" fill="none" stroke="currentColor" strokeWidth="28" />
      </svg>
      <p className="text-sm font-semibold text-slab-muted">Disponible real</p>
      <p className="display num mt-1 text-[clamp(44px,12vw,64px)] leading-[0.95] font-bold">
        {monto(animado === disponible ? disponible : Math.round(animado))}
      </p>
      <p className="mt-2 max-w-[34ch] text-[13px] text-slab-muted">
        Lo que tenés en cuentas menos lo que vence en tus tarjetas.
      </p>
      <div className="mt-6 flex h-2.5 gap-[3px] overflow-hidden rounded-full bg-white/10">
        {(enCuentas > 0 || deuda > 0) && (
          <>
            <div className="suave rounded-full bg-[#8fb0ff]" style={{ width: `${pctLibre}%` }} />
            <div className="suave rounded-full bg-[#ffab73]" style={{ width: `${100 - pctLibre}%` }} />
          </>
        )}
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-3 text-[13px]">
        <div>
          <dt className="flex items-center gap-1.5 text-slab-muted"><i className="h-2 w-2 rounded-full bg-[#8fb0ff]" />En cuentas</dt>
          <dd className="num mt-0.5 text-base font-bold">{monto(enCuentas)}</dd>
        </div>
        <div>
          <dt className="flex items-center gap-1.5 text-slab-muted"><i className="h-2 w-2 rounded-full bg-[#ffab73]" />A pagar en tarjetas</dt>
          <dd className="num mt-0.5 text-base font-bold">{monto(deuda)}</dd>
        </div>
      </dl>
      {futuras > 0 && (
        <p className="mt-3 text-[13px] text-slab-muted">
          Además, <b className="num text-slab-ink">{monto(futuras)}</b> en cuotas de los próximos resúmenes.
        </p>
      )}
      {usd && Number(usd.disponible) !== 0 && (
        <p className="mt-4 border-t border-white/10 pt-3 text-[13px] text-slab-muted">
          Además tenés <b className="num text-slab-ink">{monto(usd.disponible, "USD")}</b>
        </p>
      )}
    </section>
  );
}

function Avisos({ tarjetas, deudas }: { tarjetas: Tarjeta[]; deudas: Deuda[] }) {
  const items: React.ReactNode[] = [];
  const hoy = new Date().toISOString().slice(0, 10);
  const enDiezDias = new Date(Date.now() + 10 * 86400000).toISOString().slice(0, 10);
  for (const d of deudas) {
    if (d.tipo === "prestamo" && d.proximo_vencimiento && d.proximo_vencimiento <= enDiezDias && d.cuota_sugerida) {
      items.push(
        <Link key={d.id} href="/deudas" className="press flex items-center gap-3 px-4 py-3.5 hover:bg-surface-2">
          <HandCoins size={20} className="shrink-0 text-warn" />
          <span className="text-sm"><b>{d.nombre}</b>: cuota de <b className="num">{monto(d.cuota_sugerida)}</b> el {fechaCorta(d.proximo_vencimiento)}</span>
        </Link>
      );
    }
  }
  for (const t of tarjetas) {
    const r = t.ultimo_resumen;
    if (r?.fecha_vencimiento && r.fecha_vencimiento >= hoy && r.total_ars && Number(t.deuda) > 0) {
      items.push(
        <Link key={t.cuenta_id + "v"} href={`/tarjetas/${t.cuenta_id}`} className="press flex items-center gap-3 px-4 py-3.5 hover:bg-surface-2">
          <CreditCard size={20} className="shrink-0 text-warn" />
          <span className="text-sm"><b>{t.nombre}</b> vence el {fechaCorta(r.fecha_vencimiento)}: <b className="num">{monto(r.total_ars)}</b></span>
        </Link>
      );
    }
    if (t.liberacion) {
      items.push(
        <Link key={t.cuenta_id + "l"} href={`/tarjetas/${t.cuenta_id}`} className="press flex items-center gap-3 px-4 py-3.5 hover:bg-surface-2">
          <TrendingDown size={20} className="shrink-0 text-ok" />
          <span className="text-sm">
            En {nombrePeriodo(t.liberacion.periodo)} se te liberan <b className="num">{monto(t.liberacion.monto)}</b> por mes de cuotas de la {t.nombre}
          </span>
        </Link>
      );
    }
  }
  if (!items.length) return null;
  return <div className="overflow-hidden rounded-[22px] bg-surface shadow-soft [&>*+*]:border-t [&>*+*]:border-line">{items}</div>;
}

function frase(r: Resumen): string {
  const [, mes] = r.mes.split("-").map(Number);
  const anterior = MESES[(mes + 10) % 12];
  const g = Number(r.gastos);
  const a = Number(r.gastos_anterior_a_la_fecha);
  if (g === 0) return "Todavía no registraste gastos este mes.";
  const base = `Gastaste ${monto(g)} en ${r.dia_hoy ?? r.dias_mes} ${r.dia_hoy === 1 ? "día" : "días"}.`;
  if (a <= 0) return base;
  const dif = g - a;
  const pct = Math.round((Math.abs(dif) / a) * 100);
  if (pct < 3) return `${base} Vas casi igual que en ${anterior} a esta altura.`;
  return `${base} Vas ${monto(Math.abs(dif))} ${dif < 0 ? "por debajo" : "por encima"} de ${anterior} a esta altura (${pct}% ${dif < 0 ? "menos" : "más"}).`;
}

function proyeccion(r: Resumen): string | null {
  if (!r.dia_hoy || r.dia_hoy < 5 || Number(r.gastos) === 0) return null;
  const p = (Number(r.gastos) / r.dia_hoy) * r.dias_mes;
  return `A este ritmo cerrarías el mes cerca de ${monto(Math.round(p / 1000) * 1000)}.`;
}

function EtiquetaActiva({ nombre, onApagar }: { nombre: string; onApagar: () => void }) {
  return (
    <div data-cat="pink" className="-mt-3 flex items-center gap-3 rounded-[20px] bg-[var(--cat-bg)] p-3 pl-4 text-[var(--cat-fg)]">
      <Hash size={18} className="shrink-0" />
      <span className="min-w-0 flex-1 text-sm font-semibold">
        <Link href={`/etiquetas/${nombre}`} className="font-extrabold underline-offset-2 hover:underline">#{nombre}</Link> está activa: todo lo que cargues la lleva.
      </span>
      <button onClick={onApagar} className="press min-h-9 shrink-0 rounded-xl bg-surface px-3 text-[13px] font-bold text-ink">Apagar</button>
    </div>
  );
}

export default function InicioPage() {
  const { abrirCaptura } = useApp();
  const { data: inicio, error } = useSWR<Inicio>("/inicio");
  const { data: cuentas } = useSWR<Cuenta[]>("/cuentas");
  const { data: resumen } = useSWR<Resumen>("/resumen");
  const { data: bandeja } = useSWR<Movimiento[]>("/movimientos?estado=pendiente");
  const { data: ultimos } = useSWR<Movimiento[]>("/movimientos?estado=confirmado&limit=6");
  const { data: tarjetas } = useSWR<Tarjeta[]>("/tarjetas");
  const { data: deudas } = useSWR<Deuda[]>("/deudas");
  const { data: hallazgos } = useSWR<Hallazgo[]>("/hallazgos");
  const { data: plan } = useSWR<Presupuesto>("/plan");
  const { data: metas } = useSWR<Meta[]>("/metas");
  const { data: calendario } = useSWR<CalendarioPlan>(plan?.configurado ? "/plan/calendario" : null);
  const { data: etiquetas, mutate: mutarEtiquetas } = useSWR<Etiquetas>("/etiquetas");
  const [enCola, setEnCola] = useState(0);
  useEffect(() => setEnCola(cantidadEnCola()), [inicio]);

  const hoy = new Date();
  const saludo = `${MESES[hoy.getMonth()][0].toUpperCase()}${MESES[hoy.getMonth()].slice(1)} ${hoy.getFullYear()}`;

  if (error) {
    return (
      <div className="mt-10 flex flex-col items-start gap-3">
        <CloudOff size={32} className="text-faint" />
        <h1 className="display text-3xl font-bold">No llego al servidor</h1>
        <p className="max-w-[40ch] text-muted">Revisá que gyrfinanzas esté corriendo en la compu. Igual podés cargar: lo guardo y lo envío cuando vuelva la conexión.</p>
        <Boton variante="acento" onClick={abrirCaptura}><Plus size={18} /> Cargar algo</Boton>
      </div>
    );
  }

  if (cuentas && cuentas.length === 0) {
    return (
      <div className="mt-6 flex max-w-lg flex-col gap-4">
        <h1 className="display text-[40px] leading-[1] font-bold">Empecemos por dónde tenés la plata</h1>
        <p className="text-muted">Tu banco, Mercado Pago, el efectivo y cada tarjeta. Con eso ya podés cargar gastos escribiéndolos como te salgan.</p>
        <Link href="/cuentas" className="press inline-flex min-h-12 w-fit items-center justify-center rounded-2xl bg-ink px-5 font-bold text-ground">
          Crear mis cuentas
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-7">
      <header className="flex items-center justify-between">
        <span className="text-sm font-semibold text-muted">{saludo}</span>
        <div className="flex items-center gap-2 lg:hidden"><BotonDiscreto /><SelectorTema compacto /></div>
      </header>

      {etiquetas?.activa && <EtiquetaActiva nombre={etiquetas.activa} onApagar={async () => { await api.put("/etiquetas/activa", { nombre: null }); mutarEtiquetas(); }} />}

      <div className="grid grid-cols-1 gap-7 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] lg:items-start lg:gap-10">
        <div className="flex min-w-0 flex-col gap-7">
          <HoyCard p={plan} cal={calendario} />
          <RachaCard />
          {inicio ? <Disponible inicio={inicio} /> : <Esqueleto className="h-[260px] rounded-[28px]" />}
          {tarjetas && deudas && <Avisos tarjetas={tarjetas} deudas={deudas} />}

          {enCola > 0 && (
            <p className="flex items-center gap-2 rounded-2xl bg-accent-soft p-3 text-sm font-semibold">
              <CloudOff size={18} className="text-accent" /> {enCola} cargas esperando conexión
            </p>
          )}

          <Seccion titulo="Cómo venís este mes">
            {resumen ? (
              <div className="flex flex-col gap-4 rounded-[22px] bg-surface p-5 shadow-soft">
                <p className="max-w-[52ch] text-[15px] leading-snug font-semibold">
                  {frase(resumen)} {proyeccion(resumen) && <span className="text-muted">{proyeccion(resumen)}</span>}
                </p>
                <RitmoChart r={resumen} />
              </div>
            ) : (
              <Esqueleto className="h-[280px] rounded-[22px]" />
            )}
          </Seccion>

          <Seccion
            titulo="En qué se fue"
            extra={resumen && <span className="num text-sm font-semibold text-muted">{monto(resumen.gastos)}</span>}
          >
            {resumen ? (
              resumen.por_categoria.length ? (
                <div className="rounded-[22px] bg-surface p-5 shadow-soft">
                  <CategoriasBarras items={resumen.por_categoria} total={Number(resumen.gastos)} />
                </div>
              ) : (
                <Vacio titulo="Sin gastos este mes">Cuando cargues gastos, acá vas a ver en qué categorías se va la plata.</Vacio>
              )
            ) : (
              <Esqueleto className="h-[220px] rounded-[22px]" />
            )}
          </Seccion>
        </div>

        <div className="flex min-w-0 flex-col gap-7 lg:sticky lg:top-10">
          <Seccion
            titulo="Bandeja"
            extra={
              <span className="text-[13px] font-semibold text-muted">
                {bandeja?.length ? `${bandeja.length} por confirmar` : ""}
              </span>
            }
          >
            {!bandeja && <Esqueleto className="h-[150px] rounded-[22px]" />}
            {bandeja?.map((m) => <BandejaItem key={m.id} mov={m} />)}
            {bandeja && bandeja.length === 0 && (
              <div className="flex items-center gap-3 rounded-[22px] border border-dashed border-line-strong p-4">
                <Sparkles size={20} className="shrink-0 text-ok" />
                <p className="text-sm text-muted"><b className="text-ink">Nada pendiente.</b> Lo que cargues sin medio de pago, o desde Telegram, espera acá.</p>
              </div>
            )}
            {bandeja && bandeja.length > 0 && (
              <p className="text-xs text-faint">Deslizá a la derecha para confirmar o a la izquierda para borrar.</p>
            )}
          </Seccion>

          {hallazgos && hallazgos.filter((h) => h.tono === "aviso").length > 0 && (
            <Seccion titulo="Para mirar" extra={<Link href="/semana" className="text-sm font-bold text-accent">Ver todo</Link>}>
              <Lista>{hallazgos.filter((h) => h.tono === "aviso").slice(0, 3).map((h) => <HallazgoFila key={h.clave} h={h} />)}</Lista>
            </Seccion>
          )}

          {metas && metas.filter((m) => !m.cumplida).length > 0 && (
            <Seccion titulo="Tus metas" extra={<Link href="/metas" className="text-sm font-bold text-accent">Ver todas</Link>}>
              <Lista>
                {metas.filter((m) => !m.cumplida).slice(0, 3).map((m) => (
                  <Link key={m.id} href="/metas" className="press flex items-center gap-3 px-4 py-3 hover:bg-surface-2">
                    <Anillo meta={m} size={44} />
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className="truncate text-sm font-bold">{m.nombre}</span>
                      <span className="num text-[13px] text-muted">{monto(m.ahorrado, m.moneda)} de {monto(m.objetivo, m.moneda)}</span>
                    </span>
                    <span className="num text-sm font-extrabold text-muted">{Math.round(m.progreso * 100)}%</span>
                  </Link>
                ))}
              </Lista>
            </Seccion>
          )}

          <Link href="/semana" className="press flex items-center gap-3 rounded-[22px] bg-surface p-4 shadow-soft hover:bg-surface-2">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[14px] bg-accent-soft text-accent"><CalendarRange size={20} /></span>
            <span className="flex flex-1 flex-col">
              <span className="font-bold">Tu semana</span>
              <span className="text-[13px] text-muted">Resumen de la semana pasada y repaso de 5 gastos</span>
            </span>
          </Link>

          {inicio && inicio.sin_comprobante_mes > 0 && (
            <Link
              href="/movimientos?filtro=sin_comprobante"
              className="press flex items-center gap-3 rounded-[22px] bg-warn-soft p-4 text-warn-ink"
            >
              <Paperclip size={20} className="shrink-0" />
              <span className="text-sm font-semibold">
                {inicio.sin_comprobante_mes} {inicio.sin_comprobante_mes === 1 ? "gasto de este mes no tiene" : "gastos de este mes no tienen"} comprobante. Revisalos.
              </span>
            </Link>
          )}

          <Seccion titulo="Últimos movimientos" extra={<Link href="/movimientos" className="text-sm font-bold text-accent">Ver todos</Link>}>
            {ultimos ? (
              ultimos.length ? (
                <Lista>{ultimos.map((m) => <MovimientoFila key={m.id} mov={m} />)}</Lista>
              ) : (
                <Vacio titulo="Todavía no hay movimientos" accion={<Boton variante="acento" onClick={abrirCaptura}><Plus size={18} /> Cargar el primero</Boton>}>
                  Probá escribir «café 2500 mp».
                </Vacio>
              )
            ) : (
              <Esqueleto className="h-[200px] rounded-[22px]" />
            )}
          </Seccion>
        </div>
      </div>
    </div>
  );
}
