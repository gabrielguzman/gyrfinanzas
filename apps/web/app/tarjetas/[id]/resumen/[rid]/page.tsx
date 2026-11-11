"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import useSWR from "swr";
import { AlertTriangle, ArrowLeft, Check, FileText, Link2 } from "lucide-react";
import { useApp } from "@/components/Shell";
import { Boton, Campo, Mensaje, cx, inputCls } from "@/components/ui";
import { api, ApiError, type LineaResumen, type ResumenTarjeta } from "@/lib/api";
import { fechaCorta, monto, nombrePeriodo } from "@/lib/format";
import { vibrar } from "@/lib/hooks";

const PASOS = ["Leer", "Verificar", "Conciliar"];
const TIPO: Record<string, string> = {
  consumo: "Consumo", cuota: "Cuota", impuesto: "Impuesto", interes: "Interés", cargo: "Cargo", pago: "Pago", ajuste: "Bonificación",
};

function Pasos({ paso }: { paso: number }) {
  return (
    <ol className="grid grid-cols-3 gap-2" aria-label="Pasos">
      {PASOS.map((p, i) => (
        <li key={p} className="flex flex-col gap-1.5" aria-current={paso === i ? "step" : undefined}>
          <span className="suave h-1 rounded-full" style={{ background: i <= paso ? "var(--accent)" : "var(--line)" }} />
          <span className={cx("text-xs font-bold", paso === i ? "text-ink" : "text-faint")}>{p}</span>
        </li>
      ))}
    </ol>
  );
}

function Leyendo() {
  return (
    <div className="flex flex-col gap-5">
      <h2 className="display text-[30px] leading-tight font-bold">Leyendo tu resumen…</h2>
      <div className="h-1.5 overflow-hidden rounded-full bg-line">
        <div className="esqueleto h-full w-full rounded-full" style={{ background: "linear-gradient(90deg, var(--accent-soft), var(--accent), var(--accent-soft))", backgroundSize: "200% 100%" }} />
      </div>
      <p className="max-w-[46ch] text-muted">Busco el cierre, el vencimiento, el total y cada consumo, cuota e impuesto. Tarda unos segundos.</p>
    </div>
  );
}

function FilaLinea({ l, onAccion, deshabilitado }: { l: LineaResumen; onAccion?: (a: "crear" | "ignorar") => void; deshabilitado?: boolean }) {
  return (
    <div className={cx("flex items-center gap-3 px-4 py-3", l.accion === "ignorar" && "opacity-55")}>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="flex items-center gap-1.5 text-[15px] font-bold">
          <span className="truncate">{l.descripcion}</span>
          {l.cuota_total && l.cuota_total > 1 && (
            <span className="shrink-0 rounded-md bg-accent-soft px-1.5 py-0.5 text-[11px] font-bold text-accent">{l.cuota_n}/{l.cuota_total}</span>
          )}
        </span>
        <span className="truncate text-[13px] text-muted">
          {[fechaCorta(l.fecha), l.tipo !== "consumo" && l.tipo !== "cuota" ? TIPO[l.tipo] : null, l.movimiento ? `ya cargado como ${l.movimiento}` : null]
            .filter(Boolean).join(" · ")}
        </span>
      </div>
      <span className="num shrink-0 font-extrabold">{monto(l.monto, l.moneda, l.tipo === "pago" || l.tipo === "ajuste" ? "-" : undefined)}</span>
      {onAccion && (
        <button
          disabled={deshabilitado}
          onClick={() => onAccion(l.accion === "ignorar" ? "crear" : "ignorar")}
          aria-pressed={l.accion !== "ignorar"}
          aria-label={l.accion === "ignorar" ? `Cargar ${l.descripcion}` : `No cargar ${l.descripcion}`}
          className={cx(
            "press flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border",
            l.accion === "ignorar" ? "border-line-strong text-faint" : "border-ok bg-ok text-white"
          )}
        >
          <Check size={17} strokeWidth={3} />
        </button>
      )}
    </div>
  );
}

function Grupo({ titulo, nota, lineas, onAccion, deshabilitado }: {
  titulo: string; nota?: string; lineas: LineaResumen[]; onAccion?: (l: LineaResumen, a: "crear" | "ignorar") => void; deshabilitado?: boolean;
}) {
  if (!lineas.length) return null;
  const total = lineas.filter((l) => l.moneda === "ARS").reduce((a, l) => a + Number(l.monto), 0);
  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between gap-3 px-1">
        <h3 className="font-extrabold">{titulo} <span className="font-semibold text-muted">({lineas.length})</span></h3>
        <span className="num text-[13px] font-semibold text-muted">{monto(total)}</span>
      </div>
      {nota && <p className="-mt-1 px-1 text-[13px] text-muted">{nota}</p>}
      <div className="overflow-hidden rounded-[22px] bg-surface shadow-soft [&>*+*]:border-t [&>*+*]:border-line">
        {lineas.map((l) => <FilaLinea key={l.id} l={l} onAccion={onAccion ? (a) => onAccion(l, a) : undefined} deshabilitado={deshabilitado} />)}
      </div>
    </section>
  );
}

function Verificar({ r, onSeguir, onCambio }: { r: ResumenTarjeta; onSeguir: () => void; onCambio: (d: Record<string, string>) => Promise<void> }) {
  const v = r.verificacion!;
  const [editar, setEditar] = useState(!r.fecha_cierre || !r.total_ars);
  const [cierre, setCierre] = useState(r.fecha_cierre ?? "");
  const [venc, setVenc] = useState(r.fecha_vencimiento ?? "");
  const [total, setTotal] = useState(r.total_ars ?? "");
  const [anterior, setAnterior] = useState(r.saldo_anterior ?? "");
  const pt = v.por_tipo;
  const filas: [string, string, "+" | "-" | ""][] = [
    ["Saldo del resumen anterior", v.saldo_anterior, ""],
    ["Consumos", pt.consumo, "+"],
    ["Cuotas", pt.cuota, "+"],
    ["Impuestos, intereses y cargos", String(Number(pt.impuesto) + Number(pt.interes) + Number(pt.cargo)), "+"],
    ["Pagos y bonificaciones", v.pagos_y_ajustes, "-"],
  ];
  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <span className={cx("anim-pop flex h-12 w-12 shrink-0 items-center justify-center rounded-full", v.cuadra ? "bg-ok-soft text-ok" : "bg-warn-soft text-warn-ink")}>
          {v.cuadra ? <Check size={26} strokeWidth={3} /> : <AlertTriangle size={24} />}
        </span>
        <div>
          <h2 className="display text-[28px] leading-tight font-bold">{v.cuadra ? "Cuadra con el total" : v.diferencia == null ? "Falta el total" : "No cuadra del todo"}</h2>
          <p className="text-sm text-muted">
            {v.cuadra
              ? `Leí ${r.lineas.length} líneas y suman exactamente lo que dice el PDF.`
              : v.diferencia == null
                ? "No encontré el total del resumen. Cargalo abajo para poder comparar."
                : `Hay ${monto(Math.abs(Number(v.diferencia)))} de diferencia. Puede faltar una línea o algo estar en dólares; revisalo en el paso siguiente.`}
          </p>
        </div>
      </div>

      <div className="overflow-hidden rounded-[22px] bg-surface shadow-soft">
        {filas.map(([k, val, s]) => (
          <div key={k} className="flex justify-between gap-3 border-b border-line px-4 py-3 text-sm">
            <span className="text-muted">{k}</span>
            <span className="num font-bold">{s === "-" ? "− " : s === "+" ? "+ " : ""}{monto(val)}</span>
          </div>
        ))}
        <div className="flex justify-between gap-3 bg-surface-2 px-4 py-3 text-sm">
          <span className="font-bold">Lo que leí suma</span>
          <span className="num font-extrabold">{monto(v.calculado)}</span>
        </div>
        <div className="flex justify-between gap-3 px-4 py-3 text-sm">
          <span className="font-bold">Total del PDF</span>
          <span className={cx("num font-extrabold", v.cuadra ? "text-ok" : "text-warn-ink")}>{v.total ? monto(v.total) : "—"}</span>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-2xl bg-surface p-3"><dt className="text-muted">Cierre</dt><dd className="font-bold">{fechaCorta(r.fecha_cierre)}</dd></div>
        <div className="rounded-2xl bg-surface p-3"><dt className="text-muted">Vencimiento</dt><dd className="font-bold">{fechaCorta(r.fecha_vencimiento)}</dd></div>
        <div className="rounded-2xl bg-surface p-3"><dt className="text-muted">Pago mínimo</dt><dd className="num font-bold">{r.pago_minimo ? monto(r.pago_minimo) : "—"}</dd></div>
        <div className="rounded-2xl bg-surface p-3"><dt className="text-muted">TNA</dt><dd className="num font-bold">{r.tna ? `${Number(r.tna).toLocaleString("es-AR")}%` : "—"}</dd></div>
      </dl>

      {!editar ? (
        <button onClick={() => setEditar(true)} className="w-fit text-sm font-bold text-accent">Corregir fechas o totales</button>
      ) : (
        <div className="flex flex-col gap-3 rounded-[22px] border border-line-strong p-4">
          <div className="grid grid-cols-2 gap-3">
            <Campo label="Fecha de cierre"><input type="date" className={inputCls} value={cierre} onChange={(e) => setCierre(e.target.value)} /></Campo>
            <Campo label="Vencimiento"><input type="date" className={inputCls} value={venc} onChange={(e) => setVenc(e.target.value)} /></Campo>
            <Campo label="Total del resumen"><input className={inputCls + " num"} inputMode="decimal" value={total} onChange={(e) => setTotal(e.target.value)} /></Campo>
            <Campo label="Saldo anterior"><input className={inputCls + " num"} inputMode="decimal" value={anterior} onChange={(e) => setAnterior(e.target.value)} /></Campo>
          </div>
          <Boton variante="linea" onClick={async () => {
            const d: Record<string, string> = {};
            if (cierre) d.fecha_cierre = cierre;
            if (venc) d.fecha_vencimiento = venc;
            if (total) d.total_ars = total.replace(/\./g, "").replace(",", ".");
            if (anterior) d.saldo_anterior = anterior.replace(/\./g, "").replace(",", ".");
            await onCambio(d);
            setEditar(false);
          }}>Guardar correcciones</Boton>
        </div>
      )}

      <Boton variante="acento" className="min-h-13 text-base" onClick={onSeguir} disabled={!r.fecha_cierre}>Siguiente</Boton>
    </div>
  );
}

export default function ResumenPage() {
  const { id, rid } = useParams<{ id: string; rid: string }>();
  const router = useRouter();
  const { aviso, refrescar } = useApp();
  const { data: r, mutate, error } = useSWR<ResumenTarjeta>(`/resumenes/${rid}`, {
    refreshInterval: (d) => (d?.estado === "procesando" ? 1200 : 0),
  });
  const [paso, setPaso] = useState<1 | 2>(1);
  const [ocupado, setOcupado] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const grupos = useMemo(() => {
    const ls = r?.lineas ?? [];
    return {
      cargados: ls.filter((l) => l.accion === "vincular" && l.movimiento_id),
      planes: ls.filter((l) => l.accion === "vincular" && !l.movimiento_id),
      nuevos: ls.filter((l) => l.tipo !== "pago" && (l.accion === "crear" || (l.accion === "ignorar" && !l.movimiento_id && !l.plan_id))),
      pagos: ls.filter((l) => l.tipo === "pago"),
    };
  }, [r]);

  async function patch(fn: () => Promise<ResumenTarjeta>) {
    setOcupado(true);
    setErr(null);
    try {
      await mutate(await fn(), { revalidate: false });
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "No pude conectar con el servidor");
    } finally {
      setOcupado(false);
    }
  }

  const pasoVisible = !r || r.estado === "procesando" ? 0 : r.estado === "revision" ? paso : 2;

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div className="flex items-center gap-3">
        <Link href={`/tarjetas/${id}`} aria-label="Volver a la tarjeta" className="press flex h-11 w-11 items-center justify-center rounded-full bg-surface shadow-soft">
          <ArrowLeft size={20} />
        </Link>
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="text-[13px] font-semibold text-muted">{r?.cuenta ?? "Tarjeta"}</span>
          <h1 className="text-lg leading-tight font-extrabold">
            {r?.fecha_cierre ? `Resumen de ${nombrePeriodo(r.fecha_cierre.slice(0, 7))}` : "Resumen nuevo"}
          </h1>
        </div>
        {r?.archivo_id && (
          <a href={api.urlArchivo(r.archivo_id)} target="_blank" rel="noreferrer" aria-label="Ver el PDF" className="press ml-auto flex h-11 shrink-0 items-center gap-1.5 rounded-full bg-surface px-3.5 text-sm font-bold shadow-soft">
            <FileText size={16} /> <span className="hidden sm:inline">Ver PDF</span>
          </a>
        )}
      </div>

      {r?.estado !== "error" && <Pasos paso={pasoVisible} />}

      {error && <Mensaje tono="error">No encontré ese resumen.</Mensaje>}
      {(!r || r.estado === "procesando") && !error && <Leyendo />}

      {r?.estado === "error" && (
        <div className="flex flex-col gap-4">
          <h2 className="display text-[28px] font-bold">No pude leerlo</h2>
          <Mensaje tono="error">{r.error}</Mensaje>
          <p className="text-sm text-muted">Probá con el PDF original que descargás del home banking (no una foto ni un escaneo). Si tu banco usa un formato raro, la lectura con IA lo resuelve: se activa poniendo una clave de Anthropic en la configuración.</p>
          <Boton variante="linea" onClick={async () => { await api.del(`/resumenes/${r.id}`); router.push(`/tarjetas/${id}`); }}>Descartar y volver</Boton>
        </div>
      )}

      {r?.estado === "revision" && r.verificacion && paso === 1 && (
        <Verificar r={r} onSeguir={() => setPaso(2)} onCambio={(d) => patch(() => api.patch<ResumenTarjeta>(`/resumenes/${r.id}`, d))} />
      )}

      {r?.estado === "revision" && paso === 2 && (
        <div className="flex flex-col gap-6">
          <div>
            <h2 className="display text-[28px] leading-tight font-bold">Comparado con lo que cargaste</h2>
            <p className="text-sm text-muted">Lo que ya tenías queda enlazado al PDF. Lo nuevo se carga al confirmar; destildá lo que no quieras cargar.</p>
          </div>
          {grupos.cargados.length > 0 && (
            <div className="flex items-center gap-3 rounded-[20px] bg-ok-soft p-4">
              <Link2 size={22} className="shrink-0 text-ok" />
              <p className="text-sm"><b>{grupos.cargados.length} {grupos.cargados.length === 1 ? "consumo coincide" : "consumos coinciden"}</b> con gastos que ya habías cargado.</p>
            </div>
          )}
          <Grupo
            titulo="No los tenías cargados"
            lineas={grupos.nuevos}
            onAccion={(l, a) => patch(() => api.patch<ResumenTarjeta>(`/resumenes/${r.id}/lineas/${l.id}`, { accion: a }))}
            deshabilitado={ocupado}
          />
          <Grupo titulo="Cuotas de planes que ya seguís" nota="Se marcan como pagadas en este resumen." lineas={grupos.planes} />
          <Grupo titulo="Ya cargados" lineas={grupos.cargados} />
          <Grupo titulo="Pagos" nota="No se cargan: los pagos del resumen se registran desde Cuentas, como transferencia." lineas={grupos.pagos} />
          {err && <Mensaje>{err}</Mensaje>}
          <div className="flex gap-2">
            <Boton variante="linea" onClick={() => setPaso(1)}>Atrás</Boton>
            <Boton
              variante="acento"
              className="min-h-13 flex-1 text-base"
              disabled={ocupado}
              onClick={async () => {
                setOcupado(true);
                setErr(null);
                try {
                  await api.post(`/resumenes/${r.id}/confirmar`);
                  vibrar();
                  refrescar();
                  const nuevos = grupos.nuevos.filter((l) => l.accion === "crear").length;
                  aviso(`Resumen confirmado${nuevos ? `: cargué ${nuevos} ${nuevos === 1 ? "movimiento" : "movimientos"}` : ""}`);
                  router.push(`/tarjetas/${id}`);
                } catch (e) {
                  setErr(e instanceof ApiError ? e.message : "No pude conectar con el servidor");
                  setOcupado(false);
                }
              }}
            >
              Confirmar resumen
            </Boton>
          </div>
        </div>
      )}

      {r?.estado === "confirmado" && (
        <div className="flex flex-col gap-4">
          <h2 className="display text-[28px] font-bold">Resumen confirmado</h2>
          <Grupo titulo="Líneas" lineas={r.lineas} />
          <Link href={`/tarjetas/${id}`} className="font-bold text-accent">Volver a la tarjeta</Link>
        </div>
      )}
    </div>
  );
}
