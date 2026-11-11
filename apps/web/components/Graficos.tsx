"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { CategoriaTotal, Resumen } from "@/lib/api";
import { compacto, MESES, monto } from "@/lib/format";
import { IconoCat } from "./ui";

/** Gasto acumulado día a día: este mes contra el anterior. */
export function RitmoChart({ r }: { r: Resumen }) {
  // El gráfico se dibuja al ancho real del contenedor: el texto queda en px reales.
  const caja = useRef<HTMLDivElement>(null);
  const [W, setW] = useState(600);
  useEffect(() => {
    const el = caja.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(240, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const H = W < 420 ? 190 : 230, PL = 2, PR = 2, PT = 18, PB = 24;
  const [hover, setHover] = useState<number | null>(null);
  const ref = useRef<SVGSVGElement>(null);

  const dias = r.dias_mes;
  const actual = r.diario.map((p) => Number(p.acumulado));
  const anterior = r.diario_anterior.map((p) => Number(p.acumulado));
  const maxY = Math.max(1, ...actual, ...anterior) * 1.08;
  const x = (d: number) => PL + ((d - 1) / Math.max(1, dias - 1)) * (W - PL - PR);
  const y = (v: number) => PT + (1 - v / maxY) * (H - PT - PB);
  const linea = (vals: number[]) => vals.map((v, i) => `${i ? "L" : "M"}${x(i + 1).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const area = (vals: number[]) =>
    vals.length ? `${linea(vals)} L${x(vals.length).toFixed(1)},${y(0)} L${x(1)},${y(0)} Z` : "";

  const [anio, mes] = r.mes.split("-").map(Number);
  const mesAnt = MESES[(mes + 10) % 12];
  const mesAct = MESES[mes - 1];
  // Redondeo a una escala "linda" según el tamaño (10, 100, 1.000…) y sin repetidos ni ceros
  const escala = Math.pow(10, Math.max(1, Math.floor(Math.log10(maxY / 3))));
  const grillas = [...new Set([maxY / 3, (2 * maxY) / 3].map((v) => Math.round(v / escala) * escala))].filter((g) => g > 0);
  const ticks = [1, 10, 20, dias];

  function mover(e: React.PointerEvent<SVGSVGElement>) {
    const box = ref.current!.getBoundingClientRect();
    const px = ((e.clientX - box.left) / box.width) * W;
    const d = Math.round(((px - PL) / (W - PL - PR)) * (dias - 1)) + 1;
    setHover(Math.min(dias, Math.max(1, d)));
  }

  const hv = hover ?? null;
  const vAct = hv && hv <= actual.length ? actual[hv - 1] : null;
  const vAnt = hv && hv <= anterior.length ? anterior[hv - 1] : null;
  const ultimo = actual.length ? actual[actual.length - 1] : 0;

  return (
    <figure ref={caja} className="relative m-0 min-w-0">
      <figcaption className="sr-only">
        Gasto acumulado de {mesAct}: {monto(ultimo)} al día {actual.length}. {mesAnt} cerró en{" "}
        {monto(anterior[anterior.length - 1] ?? 0)}.
      </figcaption>
      <div className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs font-semibold text-muted" aria-hidden>
        <span className="flex items-center gap-1.5"><i className="inline-block h-0.5 w-4 rounded bg-accent" /> {mesAct[0].toUpperCase() + mesAct.slice(1)}</span>
        <span className="flex items-center gap-1.5"><i className="inline-block h-0 w-4 border-t-2 border-dashed border-faint" /> {mesAnt[0].toUpperCase() + mesAnt.slice(1)}</span>
      </div>
      <svg
        ref={ref}
        viewBox={`0 0 ${W} ${H}`}
        width={W}
        height={H}
        className="block max-w-full touch-pan-y select-none"
        role="img"
        aria-label={`Ritmo de gasto de ${mesAct} ${anio} comparado con ${mesAnt}`}
        onPointerMove={mover}
        onPointerDown={mover}
        onPointerLeave={() => setHover(null)}
      >
        {grillas.map((g) => (
          <g key={g}>
            <line x1={PL} x2={W - PR} y1={y(g)} y2={y(g)} stroke="var(--line)" strokeWidth={1} />
            <text x={W - PR} y={y(g) - 6} textAnchor="end" fontSize={12} fill="var(--faint)" fontWeight={600}>{compacto(g)}</text>
          </g>
        ))}
        <line x1={PL} x2={W - PR} y1={y(0)} y2={y(0)} stroke="var(--line-strong)" strokeWidth={1} />
        {ticks.map((t) => (
          <text key={t} x={x(t)} y={H - 6} textAnchor={t === 1 ? "start" : t === dias ? "end" : "middle"} fontSize={12} fill="var(--faint)" fontWeight={600}>{t}</text>
        ))}
        <path d={linea(anterior)} fill="none" stroke="var(--faint)" strokeWidth={2} strokeDasharray="5 5" strokeLinecap="round" />
        <path d={area(actual)} fill="var(--accent)" opacity={0.1} />
        <path d={linea(actual)} fill="none" stroke="var(--accent)" strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
        {actual.length > 0 && (
          <circle cx={x(actual.length)} cy={y(ultimo)} r={5} fill="var(--accent)" stroke="var(--surface)" strokeWidth={2} />
        )}
        {hv && (
          <g>
            <line x1={x(hv)} x2={x(hv)} y1={PT} y2={y(0)} stroke="var(--line-strong)" strokeWidth={1} />
            {vAnt != null && <circle cx={x(hv)} cy={y(vAnt)} r={4} fill="var(--faint)" stroke="var(--surface)" strokeWidth={2} />}
            {vAct != null && <circle cx={x(hv)} cy={y(vAct)} r={5} fill="var(--accent)" stroke="var(--surface)" strokeWidth={2} />}
          </g>
        )}
      </svg>
      {hv && (
        <div
          className="pointer-events-none absolute top-8 z-10 rounded-xl bg-ink px-3 py-2 text-xs font-semibold text-ground shadow-soft"
          style={{ left: `${(x(hv) / W) * 100}%`, transform: `translateX(${hv > dias / 2 ? "-105%" : "5%"})` }}
        >
          <div className="mb-1 opacity-70">Día {hv}</div>
          <div className="num">{mesAct}: {vAct != null ? monto(vAct) : "—"}</div>
          <div className="num opacity-80">{mesAnt}: {vAnt != null ? monto(vAnt) : "—"}</div>
        </div>
      )}
    </figure>
  );
}

/** En qué se fue la plata: filas con ícono, barra proporcional y monto. */
export function CategoriasBarras({ items, total, max = 6 }: { items: CategoriaTotal[]; total: number; max?: number }) {
  const filas = useMemo(() => {
    if (items.length <= max) return items;
    const resto = items.slice(max - 1);
    const otras: CategoriaTotal = {
      categoria_id: null, nombre: `Otras ${resto.length}`, icono: "otros", color: "slate",
      total: String(resto.reduce((a, c) => a + Number(c.total), 0)), cantidad: resto.reduce((a, c) => a + c.cantidad, 0),
    };
    return [...items.slice(0, max - 1), otras];
  }, [items, max]);
  const mayor = Math.max(1, ...filas.map((f) => Number(f.total)));

  return (
    <ul className="flex flex-col gap-3.5" aria-label="Gasto por categoría">
      {filas.map((c) => {
        const v = Number(c.total);
        const pct = total > 0 ? Math.round((v / total) * 100) : 0;
        return (
          <li key={c.nombre} className="flex items-center gap-3" title={`${c.cantidad} ${c.cantidad === 1 ? "movimiento" : "movimientos"}`}>
            <IconoCat icono={c.icono} color={c.color} size={36} />
            <div className="flex min-w-0 flex-1 flex-col gap-1.5">
              <div className="flex items-baseline justify-between gap-2 text-sm">
                <span className="truncate font-bold">{c.nombre}</span>
                <span className="num shrink-0 font-bold">
                  {monto(v)} <span className="font-semibold text-faint">{pct}%</span>
                </span>
              </div>
              <div className="h-2 rounded-full bg-surface-2" data-cat={c.color}>
                <div className="suave h-full rounded-full" style={{ width: `${(v / mayor) * 100}%`, background: "var(--cat-fg)" }} />
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

/** Saldo total de deudas mes a mes, comparando dos estrategias. */
export function SaldoDeudasChart({
  a,
  b,
  nombreA,
  nombreB,
  inicio,
}: {
  a: number[];
  b: number[];
  nombreA: string;
  nombreB: string;
  inicio: number;
}) {
  const caja = useRef<HTMLDivElement>(null);
  const [W, setW] = useState(560);
  useEffect(() => {
    const el = caja.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(240, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const [hover, setHover] = useState<number | null>(null);
  const ref = useRef<SVGSVGElement>(null);
  const H = 180, PT = 14, PB = 22;
  const serieA = [inicio, ...a], serieB = [inicio, ...b];
  const n = Math.max(serieA.length, serieB.length);
  const maxY = Math.max(1, inicio) * 1.05;
  const x = (i: number) => (i / Math.max(1, n - 1)) * (W - 4) + 2;
  const y = (v: number) => PT + (1 - v / maxY) * (H - PT - PB);
  const path = (s: number[]) => s.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const etiquetas = [0, Math.round((n - 1) / 2), n - 1].filter((v, i, arr) => arr.indexOf(v) === i);

  return (
    <figure ref={caja} className="relative m-0 min-w-0">
      <figcaption className="sr-only">Saldo total de tus deudas mes a mes con cada estrategia.</figcaption>
      <div className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs font-semibold text-muted" aria-hidden>
        <span className="flex items-center gap-1.5"><i className="inline-block h-0.5 w-4 rounded bg-accent" /> {nombreA}</span>
        <span className="flex items-center gap-1.5"><i className="inline-block h-0 w-4 border-t-2 border-dashed border-faint" /> {nombreB}</span>
      </div>
      <svg
        ref={ref}
        width={W}
        height={H}
        viewBox={`0 0 ${W} ${H}`}
        className="block max-w-full touch-pan-y select-none"
        role="img"
        aria-label={`Saldo de deudas: ${nombreA} termina en ${a.length} meses y ${nombreB} en ${b.length}`}
        onPointerMove={(e) => {
          const box = ref.current!.getBoundingClientRect();
          setHover(Math.min(n - 1, Math.max(0, Math.round(((e.clientX - box.left) / box.width) * (n - 1)))));
        }}
        onPointerLeave={() => setHover(null)}
      >
        <line x1={0} x2={W} y1={y(0)} y2={y(0)} stroke="var(--line-strong)" />
        <text x={W - 2} y={y(inicio) + 14} textAnchor="end" fontSize={12} fontWeight={600} fill="var(--faint)">{compacto(inicio)}</text>
        {etiquetas.map((i) => (
          <text key={i} x={x(i)} y={H - 5} fontSize={12} fontWeight={600} fill="var(--faint)" textAnchor={i === 0 ? "start" : i === n - 1 ? "end" : "middle"}>
            {i === 0 ? "hoy" : `mes ${i}`}
          </text>
        ))}
        <path d={path(serieB)} fill="none" stroke="var(--faint)" strokeWidth={2} strokeDasharray="5 5" />
        <path d={path(serieA)} fill="none" stroke="var(--accent)" strokeWidth={2.5} strokeLinejoin="round" />
        {hover != null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={PT} y2={y(0)} stroke="var(--line-strong)" />
            {hover < serieB.length && <circle cx={x(hover)} cy={y(serieB[hover])} r={4} fill="var(--faint)" stroke="var(--surface)" strokeWidth={2} />}
            {hover < serieA.length && <circle cx={x(hover)} cy={y(serieA[hover])} r={5} fill="var(--accent)" stroke="var(--surface)" strokeWidth={2} />}
          </g>
        )}
      </svg>
      {hover != null && (
        <div
          className="pointer-events-none absolute top-8 z-10 rounded-xl bg-ink px-3 py-2 text-xs font-semibold text-ground shadow-soft"
          style={{ left: `${(x(hover) / W) * 100}%`, transform: `translateX(${hover > n / 2 ? "-105%" : "5%"})` }}
        >
          <div className="mb-1 opacity-70">{hover === 0 ? "Hoy" : `Mes ${hover}`}</div>
          <div className="num">{nombreA}: {monto(serieA[Math.min(hover, serieA.length - 1)])}</div>
          <div className="num opacity-80">{nombreB}: {monto(serieB[Math.min(hover, serieB.length - 1)])}</div>
        </div>
      )}
    </figure>
  );
}

/** Saldo proyectado día a día (cuentas en pesos) con los movimientos grandes marcados. */
export function SaldoProyectadoChart({
  serie,
  eventos,
}: {
  serie: { fecha: string; saldo: number }[];
  eventos: { fecha: string; monto: number; titulo: string }[];
}) {
  const caja = useRef<HTMLDivElement>(null);
  const [W, setW] = useState(560);
  useEffect(() => {
    const el = caja.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(240, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const [hover, setHover] = useState<number | null>(null);
  const ref = useRef<SVGSVGElement>(null);
  const H = 190, PT = 16, PB = 24;
  const n = serie.length;
  const valores = serie.map((p) => p.saldo);
  const maxY = Math.max(1, ...valores) * 1.08;
  const minY = Math.min(0, ...valores) * 1.08;
  const x = (i: number) => (i / Math.max(1, n - 1)) * (W - 4) + 2;
  const y = (v: number) => PT + ((maxY - v) / (maxY - minY || 1)) * (H - PT - PB);
  const linea = valores.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const area = `${linea} L${x(n - 1).toFixed(1)},${y(0).toFixed(1)} L${x(0).toFixed(1)},${y(0).toFixed(1)} Z`;
  const idx = useMemo(() => new Map(serie.map((p, i) => [p.fecha, i])), [serie]);
  const marcas = eventos.filter((e) => Math.abs(e.monto) > 0 && idx.has(e.fecha));
  const etiquetas = [0, Math.round((n - 1) / 2), n - 1].filter((v, i, arr) => arr.indexOf(v) === i);
  const etiqueta = (iso: string) => {
    const d = new Date(iso + "T12:00:00");
    return `${d.getDate()} ${MESES[d.getMonth()].slice(0, 3)}`;
  };
  const enRojo = valores.some((v) => v < 0);
  const h = hover != null ? serie[hover] : null;
  const delDia = h ? eventos.filter((e) => e.fecha === h.fecha) : [];

  return (
    <figure ref={caja} className="relative m-0 min-w-0">
      <figcaption className="sr-only">
        Saldo proyectado de tus cuentas en pesos los próximos {n - 1} días. Mínimo: {monto(Math.min(...valores))}.
      </figcaption>
      <svg
        ref={ref}
        width={W}
        height={H}
        viewBox={`0 0 ${W} ${H}`}
        className="block max-w-full touch-pan-y select-none"
        role="img"
        aria-label="Saldo proyectado"
        onPointerMove={(e) => {
          const box = ref.current!.getBoundingClientRect();
          setHover(Math.min(n - 1, Math.max(0, Math.round(((e.clientX - box.left) / box.width) * (n - 1)))));
        }}
        onPointerDown={(e) => {
          const box = ref.current!.getBoundingClientRect();
          setHover(Math.min(n - 1, Math.max(0, Math.round(((e.clientX - box.left) / box.width) * (n - 1)))));
        }}
        onPointerLeave={() => setHover(null)}
      >
        <defs>
          <clipPath id="sobre-cero"><rect x={0} y={0} width={W} height={y(0)} /></clipPath>
          <clipPath id="bajo-cero"><rect x={0} y={y(0)} width={W} height={H} /></clipPath>
        </defs>
        <path d={area} fill="var(--accent)" opacity={0.1} clipPath="url(#sobre-cero)" />
        {enRojo && <path d={area} fill="var(--danger)" opacity={0.16} clipPath="url(#bajo-cero)" />}
        <line x1={0} x2={W} y1={y(0)} y2={y(0)} stroke="var(--line-strong)" />
        <text x={W - 2} y={y(0) - 6} textAnchor="end" fontSize={12} fontWeight={600} fill="var(--faint)">$ 0</text>
        <path d={linea} fill="none" stroke="var(--accent)" strokeWidth={2.5} strokeLinejoin="round" clipPath="url(#sobre-cero)" />
        {enRojo && <path d={linea} fill="none" stroke="var(--danger)" strokeWidth={2.5} strokeLinejoin="round" clipPath="url(#bajo-cero)" />}
        {marcas.map((e, i) => {
          const k = idx.get(e.fecha)!;
          return <circle key={i} cx={x(k)} cy={y(valores[k])} r={e.monto > 0 ? 4.5 : 3} fill={e.monto > 0 ? "var(--ok)" : "var(--surface)"} stroke={e.monto > 0 ? "var(--surface)" : "var(--faint)"} strokeWidth={1.5} />;
        })}
        {etiquetas.map((i) => (
          <text key={i} x={x(i)} y={H - 5} fontSize={12} fontWeight={600} fill="var(--faint)" textAnchor={i === 0 ? "start" : i === n - 1 ? "end" : "middle"}>
            {i === 0 ? "hoy" : etiqueta(serie[i].fecha)}
          </text>
        ))}
        {hover != null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={PT} y2={H - PB} stroke="var(--line-strong)" />
            <circle cx={x(hover)} cy={y(valores[hover])} r={5} fill={valores[hover] < 0 ? "var(--danger)" : "var(--accent)"} stroke="var(--surface)" strokeWidth={2} />
          </g>
        )}
      </svg>
      {h && (
        <div
          className="pointer-events-none absolute top-0 z-10 max-w-[220px] rounded-xl bg-ink px-3 py-2 text-xs font-semibold text-ground shadow-soft"
          style={{ left: `${(x(hover!) / W) * 100}%`, transform: `translateX(${hover! > n / 2 ? "-105%" : "5%"})` }}
        >
          <div className="mb-1 opacity-70">{hover === 0 ? "Hoy" : etiqueta(h.fecha)}</div>
          <div className="num">Saldo: {monto(h.saldo)}</div>
          {delDia.map((e, i) => (
            <div key={i} className="num truncate opacity-80">{e.titulo}: {monto(Math.abs(e.monto), "ARS", e.monto > 0 ? "+" : "-")}</div>
          ))}
        </div>
      )}
    </figure>
  );
}

/** Patrimonio neto a fin de cada mes (barras) y hoy (la última, resaltada). */
export function PatrimonioChart({ puntos }: { puntos: { fecha: string; neto: number; estimado: boolean }[] }) {
  const caja = useRef<HTMLDivElement>(null);
  const [W, setW] = useState(560);
  useEffect(() => {
    const el = caja.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(240, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const H = 170, PT = 22, PB = 24;
  const n = puntos.length;
  const max = Math.max(1, ...puntos.map((p) => p.neto));
  const min = Math.min(0, ...puntos.map((p) => p.neto));
  const y = (v: number) => PT + ((max - v) / (max - min || 1)) * (H - PT - PB);
  const paso = W / Math.max(n, 1);
  const ancho = Math.min(48, paso * 0.62);
  const mes = (iso: string, i: number) => {
    if (i === n - 1) return "hoy";
    const d = new Date(iso + "T12:00:00");
    return MESES[d.getMonth()].slice(0, 3);
  };
  return (
    <figure ref={caja} className="m-0 min-w-0">
      <figcaption className="sr-only">
        Patrimonio neto por mes: {puntos.map((p) => `${p.fecha}: ${monto(p.neto)}`).join(", ")}.
      </figcaption>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="block max-w-full" aria-hidden>
        <line x1={0} x2={W} y1={y(0)} y2={y(0)} stroke="var(--line-strong)" />
        {puntos.map((p, i) => {
          const cx = paso * i + paso / 2;
          const top = Math.min(y(p.neto), y(0));
          const h = Math.max(2, Math.abs(y(p.neto) - y(0)));
          const ultimo = i === n - 1;
          return (
            <g key={p.fecha}>
              <rect x={cx - ancho / 2} y={top} width={ancho} height={h} rx={6}
                fill={p.neto < 0 ? "var(--danger)" : ultimo ? "var(--accent)" : "var(--line-strong)"}
                opacity={p.estimado ? 0.55 : 1} />
              {(ultimo || n <= 7) && (
                <text x={cx} y={top - 6} textAnchor="middle" fontSize={11} fontWeight={700} fill={ultimo ? "var(--ink)" : "var(--faint)"}>
                  {compacto(p.neto)}
                </text>
              )}
              <text x={cx} y={H - 6} textAnchor="middle" fontSize={12} fontWeight={600} fill="var(--faint)">{mes(p.fecha, i)}</text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}
