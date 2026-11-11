"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { Minus, Plus, X } from "lucide-react";
import { api, ApiError, type Cuenta, type Meta, type Moneda } from "@/lib/api";
import { fechaCorta, hoyISO, MESES, monto } from "@/lib/format";
import { vibrar } from "@/lib/hooks";
import { Sheet } from "./Sheet";
import { useApp } from "./Shell";
import { Boton, Campo, Chip, Mensaje, cx, inputCls } from "./ui";

const EMOJIS = ["🎯", "🏖️", "✈️", "🛟", "🏠", "🚗", "💻", "🎓", "💍", "🎸", "👶", "🐶"];
const num = (s: string) => s.replace(/\./g, "").replace(",", ".").replace(/[^\d.]/g, "");
const miles = (v: string | number | null | undefined) => (v == null || v === "" ? "" : Math.round(Number(v)).toLocaleString("es-AR"));

export function mesAnio(iso: string): string {
  const d = new Date(iso + "T12:00:00");
  return `${MESES[d.getMonth()]} ${d.getFullYear()}`;
}

function sumarMeses(n: number): string {
  const d = new Date();
  d.setMonth(d.getMonth() + n);
  return d.toISOString().slice(0, 10);
}

/** Anillo de progreso con el emoji adentro. */
export function Anillo({ meta, size = 64 }: { meta: Pick<Meta, "progreso" | "emoji" | "cumplida" | "en_camino">; size?: number }) {
  const r = size / 2 - 4;
  const c = 2 * Math.PI * r;
  const color = meta.cumplida ? "var(--ok)" : meta.en_camino === false ? "var(--warn)" : "var(--accent)";
  return (
    <span className="relative inline-flex shrink-0 items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-2)" strokeWidth={6} />
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={6} strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - Math.min(1, meta.progreso))} className="suave"
        />
      </svg>
      <span className="absolute" style={{ fontSize: size * 0.4 }} aria-hidden>{meta.emoji}</span>
    </span>
  );
}

/** Qué decir debajo de la meta. */
export function estadoMeta(m: Meta): { texto: string; tono: "ok" | "warn" | "normal" } {
  if (m.cumplida) return { texto: "¡Llegaste!", tono: "ok" };
  if (m.en_camino === false && m.por_mes && m.ritmo != null)
    return { texto: `Atrasada: necesitás ${monto(m.por_mes, m.moneda)} por mes y venís con ${monto(Math.max(0, Number(m.ritmo)), m.moneda)}`, tono: "warn" };
  if (m.fecha_objetivo && m.por_mes) return { texto: `Apartá ${monto(m.por_mes, m.moneda)} por mes hasta ${mesAnio(m.fecha_objetivo)}`, tono: "normal" };
  if (m.aporte_mensual && m.fecha_estimada) return { texto: `A ${monto(m.aporte_mensual, m.moneda)} por mes llegás en ${mesAnio(m.fecha_estimada)}`, tono: "normal" };
  return { texto: "Sin fecha ni aporte mensual", tono: "normal" };
}

export function MetaCard({ m, onAbrir }: { m: Meta; onAbrir: () => void }) {
  const e = estadoMeta(m);
  return (
    <button onClick={onAbrir} className="press flex w-full items-center gap-4 rounded-[22px] bg-surface p-4 text-left shadow-soft">
      <Anillo meta={m} />
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="truncate text-[15px] font-extrabold">{m.nombre}</span>
        <span className="num text-sm">
          <b>{monto(m.ahorrado, m.moneda)}</b> <span className="text-muted">de {monto(m.objetivo, m.moneda)}</span>
        </span>
        <span className={cx("text-[13px] font-semibold", e.tono === "warn" ? "text-warn-ink" : e.tono === "ok" ? "text-ok" : "text-muted")}>
          {e.texto}
        </span>
      </span>
      <span className="num shrink-0 text-lg font-extrabold text-muted">{Math.round(m.progreso * 100)}%</span>
    </button>
  );
}

export type MetaAbierta = { id: string } | { nueva: true } | null;

export function MetaSheet({ abierta, onCerrar }: { abierta: MetaAbierta; onCerrar: () => void }) {
  return (
    <Sheet abierto={!!abierta} onCerrar={onCerrar} titulo={abierta && "nueva" in abierta ? "Nueva meta" : undefined}>
      {abierta && "id" in abierta && <Detalle id={abierta.id} onCerrar={onCerrar} />}
      {abierta && "nueva" in abierta && <Formulario onListo={onCerrar} />}
    </Sheet>
  );
}

function Detalle({ id, onCerrar }: { id: string; onCerrar: () => void }) {
  const { aviso, refrescar } = useApp();
  const { data: m, mutate } = useSWR<Meta>(`/metas/${id}`);
  const [editando, setEditando] = useState(false);
  const [valor, setValor] = useState("");
  const [sacar, setSacar] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!m) return <div className="esqueleto h-64" />;
  if (editando) return <Formulario existente={m} onListo={async () => { setEditando(false); await mutate(); }} />;
  const e = estadoMeta(m);
  const rapidos = m.moneda === "USD" ? [50, 100, 500] : [10000, 50000, 100000];

  async function aportar() {
    const n = Number(num(valor));
    if (!n || !m) return;
    setOcupado(true);
    setError(null);
    try {
      const r = await api.post<Meta>(`/metas/${m.id}/aportes`, { monto: sacar ? -n : n });
      vibrar();
      await mutate(r, { revalidate: false });
      refrescar();
      setValor("");
      aviso(r.cumplida && !m.cumplida ? `¡Llegaste a ${m.nombre}! 🎉` : sacar ? `Sacaste ${monto(n, m.moneda)}` : `Sumaste ${monto(n, m.moneda)}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No pude conectar con el servidor");
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-4">
        <Anillo meta={m} size={84} />
        <div className="min-w-0 flex-1">
          <h2 className="line-clamp-2 text-xl leading-tight font-extrabold">{m.nombre}</h2>
          <p className="num text-sm"><b>{monto(m.ahorrado, m.moneda)}</b> <span className="text-muted">de {monto(m.objetivo, m.moneda)} · {Math.round(m.progreso * 100)}%</span></p>
        </div>
      </div>

      <p className={cx("rounded-2xl p-3 text-sm font-semibold", e.tono === "warn" ? "bg-warn-soft text-warn-ink" : e.tono === "ok" ? "bg-ok-soft" : "bg-surface")}>
        {e.texto}.
        {!m.cumplida && Number(m.falta) > 0 && <span className="font-normal text-muted"> Te faltan {monto(m.falta, m.moneda)}.</span>}
        {m.por_mes_ars && m.moneda === "USD" && <span className="font-normal text-muted"> Hoy son {monto(m.por_mes_ars)} por mes.</span>}
      </p>

      {m.cuenta ? (
        <p className="text-sm text-muted">
          Sigue el saldo de <b className="text-ink">{m.cuenta}</b>: cuando transferís a esa cuenta, la meta se actualiza sola.
        </p>
      ) : (
        <div className="flex flex-col gap-3 rounded-[22px] border border-line-strong p-4">
          <div className="flex gap-1.5" role="radiogroup" aria-label="Sumar o sacar">
            <Chip activo={!sacar} onClick={() => setSacar(false)}><Plus size={14} /> Sumar</Chip>
            <Chip activo={sacar} onClick={() => setSacar(true)}><Minus size={14} /> Sacar</Chip>
          </div>
          <input
            className={inputCls + " num text-lg"} inputMode="numeric" placeholder={m.moneda === "USD" ? "USD 100" : "$ 50.000"}
            value={valor} onChange={(ev) => setValor(miles(num(ev.target.value)))} aria-label="Monto"
          />
          <div className="flex flex-wrap gap-1.5">
            {rapidos.map((r) => (
              <Chip key={r} onClick={() => setValor(miles(Number(num(valor) || 0) + r))}>+{monto(r, m.moneda)}</Chip>
            ))}
            {m.por_mes && <Chip onClick={() => setValor(miles(m.por_mes))}>Lo del mes</Chip>}
          </div>
          {error && <Mensaje>{error}</Mensaje>}
          <Boton variante="acento" disabled={ocupado || !Number(num(valor))} onClick={aportar}>{sacar ? "Sacar" : "Sumar a la meta"}</Boton>
          <span className="text-xs text-faint">Desde Telegram: «aparté 50k para {m.nombre.toLowerCase()}».</span>
        </div>
      )}

      {m.aportes.length > 0 && (
        <div className="flex flex-col gap-2">
          <span className="text-[13px] font-bold">Movimientos</span>
          <div className="overflow-hidden rounded-[20px] bg-surface">
            {m.aportes.map((a, i) => (
              <div key={a.id} className={cx("flex items-center gap-3 py-1.5 pr-1.5 pl-4 text-sm", i > 0 && "border-t border-line")}>
                <span className="flex-1 text-muted">{fechaCorta(a.fecha)}{a.nota && ` · ${a.nota}`}</span>
                <span className={cx("num font-bold", Number(a.monto) < 0 && "text-warn-ink")}>{monto(Math.abs(Number(a.monto)), m.moneda, Number(a.monto) < 0 ? "-" : "+")}</span>
                <button
                  aria-label="Borrar este movimiento" className="press flex h-10 w-10 items-center justify-center rounded-xl text-faint hover:text-ink"
                  onClick={async () => { const r = await api.del<Meta>(`/metas/${m.id}/aportes/${a.id}`); await mutate(r, { revalidate: false }); refrescar(); }}
                >
                  <X size={16} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
        <button className="font-bold text-muted" onClick={() => setEditando(true)}>Editar</button>
        <button
          className="font-bold text-muted"
          onClick={async () => { await api.patch(`/metas/${m.id}`, { archivada: true }); refrescar(); aviso(`Archivada: ${m.nombre}`, { deshacer: () => api.patch(`/metas/${m.id}`, { archivada: false }) }); onCerrar(); }}
        >
          {m.cumplida ? "Archivar (ya la cumplí)" : "Archivar"}
        </button>
        <button
          className="font-bold text-danger"
          onClick={async () => { await api.del(`/metas/${m.id}`); refrescar(); aviso(`Meta borrada: ${m.nombre}`); onCerrar(); }}
        >
          Borrar
        </button>
      </div>
    </div>
  );
}

const PLAZOS = [
  { meses: 3, label: "3 meses" },
  { meses: 6, label: "6 meses" },
  { meses: 12, label: "1 año" },
];

function Formulario({ existente, onListo }: { existente?: Meta; onListo: () => void }) {
  const { aviso, refrescar } = useApp();
  const { data: cuentas } = useSWR<Cuenta[]>("/cuentas");
  const [nombre, setNombre] = useState(existente?.nombre ?? "");
  const [emoji, setEmoji] = useState(existente?.emoji ?? "🎯");
  const [objetivo, setObjetivo] = useState(miles(existente?.objetivo));
  const [moneda, setMoneda] = useState<Moneda>(existente?.moneda ?? "ARS");
  const [modo, setModo] = useState<"fecha" | "mensual">(existente && !existente.fecha_objetivo && existente.aporte_mensual ? "mensual" : "fecha");
  const [fecha, setFecha] = useState(existente?.fecha_objetivo ?? sumarMeses(6));
  const [mensual, setMensual] = useState(miles(existente?.aporte_mensual));
  const [cuenta, setCuenta] = useState<string | null>(existente?.cuenta_id ?? null);
  const [yaTengo, setYaTengo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const opciones = (cuentas ?? []).filter((c) => c.tipo !== "tarjeta_credito" && !c.archivada && c.moneda === moneda);
  useEffect(() => {
    if (cuenta && !opciones.some((c) => c.id === cuenta)) setCuenta(null);
  }, [moneda]); // eslint-disable-line react-hooks/exhaustive-deps

  async function guardar() {
    setOcupado(true);
    setError(null);
    const datos = {
      nombre: nombre.trim(), emoji, objetivo: num(objetivo),
      fecha_objetivo: modo === "fecha" ? fecha : null,
      aporte_mensual: modo === "mensual" && num(mensual) ? num(mensual) : null,
      cuenta_id: cuenta,
    };
    try {
      if (existente) await api.patch(`/metas/${existente.id}`, datos);
      else await api.post("/metas", { ...datos, moneda, ya_tengo: !cuenta && num(yaTengo) ? num(yaTengo) : null });
      vibrar();
      refrescar();
      aviso(existente ? "Meta actualizada" : `Meta creada: ${emoji} ${nombre.trim()}`);
      onListo();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No pude conectar con el servidor");
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Campo label="Para qué">
        <input className={inputCls} value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Vacaciones, fondo de emergencia, auto…" autoFocus={!existente} />
      </Campo>
      <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Ícono">
        {EMOJIS.map((e) => (
          <button
            key={e} role="radio" aria-checked={emoji === e} onClick={() => setEmoji(e)} aria-label={e}
            className={cx("press flex h-11 w-11 items-center justify-center rounded-xl text-xl", emoji === e ? "bg-ink" : "bg-surface")}
          >
            {e}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-end gap-2">
        <Campo label="Cuánto querés juntar">
          <input className={inputCls + " num"} inputMode="numeric" value={objetivo} onChange={(e) => setObjetivo(miles(num(e.target.value)))} placeholder="1.500.000" />
        </Campo>
        {!existente && (
          <div className="flex gap-1 pb-0.5" role="radiogroup" aria-label="Moneda">
            <Chip activo={moneda === "ARS"} onClick={() => setMoneda("ARS")}>$</Chip>
            <Chip activo={moneda === "USD"} onClick={() => setMoneda("USD")}>USD</Chip>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-2">
        <span className="text-[13px] font-bold">Para cuándo</span>
        <div className="flex flex-wrap gap-1.5">
          {PLAZOS.map((p) => (
            <Chip key={p.meses} activo={modo === "fecha" && fecha === sumarMeses(p.meses)} onClick={() => { setModo("fecha"); setFecha(sumarMeses(p.meses)); }}>{p.label}</Chip>
          ))}
          <label className={cx("press relative inline-flex min-h-10 cursor-pointer items-center rounded-full border px-3.5 text-[13px] font-bold",
            modo === "fecha" && !PLAZOS.some((p) => sumarMeses(p.meses) === fecha) ? "border-ink bg-ink text-ground" : "border-line-strong bg-surface")}>
            {modo === "fecha" && !PLAZOS.some((p) => sumarMeses(p.meses) === fecha) ? mesAnio(fecha) : "Otra fecha"}
            <input type="date" min={hoyISO()} value={fecha} onChange={(e) => { if (e.target.value) { setModo("fecha"); setFecha(e.target.value); } }} className="absolute inset-0 cursor-pointer opacity-0" aria-label="Elegir fecha" />
          </label>
          <Chip activo={modo === "mensual"} onClick={() => setModo("mensual")}>Sin fecha</Chip>
        </div>
        {modo === "mensual" && (
          <Campo label="Cuánto pensás poner por mes (opcional)" ayuda="Con eso te digo cuándo llegás.">
            <input className={inputCls + " num"} inputMode="numeric" value={mensual} onChange={(e) => setMensual(miles(num(e.target.value)))} />
          </Campo>
        )}
      </div>

      <div className="flex flex-col gap-2">
        <span className="text-[13px] font-bold">Dónde la guardás</span>
        <div className="flex flex-wrap gap-1.5">
          <Chip activo={!cuenta} onClick={() => setCuenta(null)}>La voy anotando</Chip>
          {opciones.map((c) => <Chip key={c.id} activo={cuenta === c.id} onClick={() => setCuenta(c.id)}>{c.nombre}</Chip>)}
        </div>
        <span className="text-xs text-faint">
          {cuenta ? "La meta sigue el saldo de esa cuenta: no hace falta anotar nada." : "Anotás lo que vas apartando, acá o por Telegram."}
        </span>
      </div>

      {!existente && !cuenta && (
        <Campo label="Ya tengo juntado (opcional)">
          <input className={inputCls + " num"} inputMode="numeric" value={yaTengo} onChange={(e) => setYaTengo(miles(num(e.target.value)))} placeholder="0" />
        </Campo>
      )}
      <p className="text-xs text-faint">Lo que la meta pide por mes se descuenta de «Hoy podés gastar».</p>
      {error && <Mensaje>{error}</Mensaje>}
      <Boton variante="acento" disabled={ocupado || !nombre.trim() || !Number(num(objetivo))} onClick={guardar}>
        {existente ? "Guardar cambios" : "Crear meta"}
      </Boton>
    </div>
  );
}
