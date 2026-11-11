"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { FileText, ShieldAlert, ShieldCheck, ShieldOff, Wrench } from "lucide-react";
import { api, ApiError, type Garantia, type Movimiento } from "@/lib/api";
import { MESES, fechaCorta, hoyISO, monto } from "@/lib/format";
import { vibrar } from "@/lib/hooks";
import { AdjuntarBoton } from "./AdjuntarBoton";
import { Sheet } from "./Sheet";
import { useApp } from "./Shell";
import { Boton, Campo, Chip, Mensaje, cx, inputCls } from "./ui";

export type GarantiaAbierta = { id: string } | { nueva: true; movimiento?: string } | null;

const DURACIONES = [
  { meses: 6, label: "6 meses" },
  { meses: 12, label: "1 año" },
  { meses: 24, label: "2 años" },
  { meses: 36, label: "3 años" },
];

/** «2 dic 2025»: en garantías el año importa. */
export function fechaAnio(iso: string): string {
  const d = new Date(iso + "T12:00:00");
  return `${fechaCorta(iso)} ${d.getFullYear()}`;
}
const mesAnio = (iso: string) => {
  const d = new Date(iso + "T12:00:00");
  return `${MESES[d.getMonth()].slice(0, 3)} ${d.getFullYear()}`;
};

export function duracion(meses: number): string {
  if (meses % 12 === 0) return meses === 12 ? "1 año" : `${meses / 12} años`;
  return meses === 1 ? "1 mes" : `${meses} meses`;
}

/** «Te quedan 11 meses», «Vence en 12 días», «Venció el 3 may»… */
export function cuandoVence(g: Pick<Garantia, "estado" | "dias_restantes" | "vence">): string {
  const d = g.dias_restantes;
  if (g.estado === "en_reparacion") return "En reparación: la garantía no corre";
  if (g.estado === "vencida") return `Venció el ${fechaAnio(g.vence)}`;
  if (d === 0) return "Vence hoy";
  if (d === 1) return "Vence mañana";
  if (d <= 60) return `Vence en ${d} días`;
  const meses = Math.round(d / 30.4);
  return meses >= 24 && meses % 12 < 2 ? `Te quedan ${Math.floor(meses / 12)} años` : `Te quedan ${meses} meses`;
}

const TONO: Record<Garantia["estado"], { Icon: typeof ShieldCheck; caja: string; barra: string }> = {
  vigente: { Icon: ShieldCheck, caja: "bg-ok-soft text-ok", barra: "var(--ok)" },
  por_vencer: { Icon: ShieldAlert, caja: "bg-warn-soft text-warn-ink", barra: "var(--warn)" },
  en_reparacion: { Icon: Wrench, caja: "bg-accent-soft text-accent", barra: "var(--accent)" },
  vencida: { Icon: ShieldOff, caja: "bg-surface-2 text-faint", barra: "var(--line-strong)" },
};

export function EscudoGarantia({ estado, size = 44 }: { estado: Garantia["estado"]; size?: number }) {
  const { Icon, caja } = TONO[estado];
  return (
    <span className={cx("flex shrink-0 items-center justify-center rounded-[14px]", caja)} style={{ width: size, height: size }} aria-hidden>
      <Icon size={size * 0.48} />
    </span>
  );
}

export function BarraGarantia({ g }: { g: Garantia }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="h-2 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(g.progreso * 100)} aria-label="Tiempo de garantía usado">
        <div className="h-full rounded-full" style={{ width: `${Math.max(3, g.progreso * 100)}%`, background: TONO[g.estado].barra }} />
      </div>
      <div className="flex justify-between text-xs font-semibold text-faint">
        <span>{mesAnio(g.fecha_compra)}</span>
        <span>vence {fechaAnio(g.vence)}</span>
      </div>
    </div>
  );
}

export function GarantiaFila({ g, onAbrir }: { g: Garantia; onAbrir: () => void }) {
  const imagen = g.archivos.find((a) => a.mime.startsWith("image/"));
  return (
    <button onClick={onAbrir} className="press flex w-full gap-3.5 px-4 py-4 text-left">
      <EscudoGarantia estado={g.estado} />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className={cx("truncate text-[15px] font-bold", g.estado === "vencida" && "text-muted")}>{g.producto}</p>
            <p className={cx("text-[13px] font-semibold", g.estado === "por_vencer" ? "text-warn-ink" : "text-muted")}>
              {cuandoVence(g)}
              {g.comercio && <span className="font-normal text-faint"> · {g.comercio}</span>}
            </p>
          </div>
          {imagen ? (
            <img src={api.urlArchivo(imagen.id)} alt="" className="h-11 w-9 shrink-0 rounded-lg object-cover" loading="lazy" />
          ) : g.archivos.length ? (
            <FileText size={20} className="mt-1 shrink-0 text-faint" aria-label="Tiene comprobante" />
          ) : null}
        </div>
        {g.estado !== "vencida" && <BarraGarantia g={g} />}
      </div>
    </button>
  );
}

/** Detalle de una garantía o alta nueva (suelta o desde un gasto). */
export function GarantiaSheet({ abierta, onCerrar }: { abierta: GarantiaAbierta; onCerrar: () => void }) {
  const id = abierta && "id" in abierta ? abierta.id : null;
  const nueva = abierta && "nueva" in abierta ? abierta : null;
  return (
    <Sheet abierto={!!abierta} onCerrar={onCerrar} titulo={nueva ? "Nueva garantía" : undefined}>
      {id && <Detalle id={id} onCerrar={onCerrar} />}
      {nueva && <Formulario movimientoId={nueva.movimiento} onListo={onCerrar} />}
    </Sheet>
  );
}

function Detalle({ id, onCerrar }: { id: string; onCerrar: () => void }) {
  const { aviso, refrescar, abrirMovimiento } = useApp();
  const { data: g, mutate } = useSWR<Garantia>(`/garantias/${id}`);
  const [editando, setEditando] = useState(false);
  const [ocupado, setOcupado] = useState(false);

  if (!g) return <div className="esqueleto h-64" />;
  if (editando) {
    return <Formulario existente={g} onListo={async () => { setEditando(false); await mutate(); }} />;
  }

  async function reparacion(accion: "enviar" | "volvio") {
    setOcupado(true);
    try {
      const r = await api.post<Garantia>(`/garantias/${id}/reparacion`, { accion });
      vibrar();
      await mutate(r, { revalidate: false });
      refrescar();
      if (accion === "enviar") aviso("Anotado. Mientras esté en el service, la garantía no corre.");
      else aviso(r.dias_reparacion > (g?.dias_reparacion ?? 0) ? `Le sumé ${r.dias_reparacion - (g?.dias_reparacion ?? 0)} días a la garantía` : "Listo, volvió");
    } finally {
      setOcupado(false);
    }
  }

  async function subir(f: File) {
    if (!g) return;
    try {
      if (g.movimiento_id) {
        await api.subir(`/movimientos/${g.movimiento_id}/adjuntos/subir`, f, { rol: "garantia" });
      } else {
        const a = await api.subir<{ id: string }>("/archivos", f);
        await api.patch(`/garantias/${g.id}`, { archivo_id: a.id });
      }
      await mutate();
      refrescar();
      aviso("Comprobante guardado");
    } catch (e) {
      aviso(e instanceof ApiError ? e.message : "No pude conectar con el servidor");
    }
  }

  const reclamar = g.estado === "por_vencer" || g.estado === "en_reparacion";
  const ROL: Record<string, string> = { garantia: "Certificado", factura: "Factura", ticket: "Ticket" };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3.5">
        <EscudoGarantia estado={g.estado} size={52} />
        <div className="min-w-0 flex-1">
          <h2 className="line-clamp-2 text-xl leading-tight font-extrabold">{g.producto}</h2>
          <p className="text-sm text-muted">
            {g.comercio ? `${g.comercio} · ` : ""}comprado el {fechaAnio(g.fecha_compra)}
          </p>
        </div>
      </div>

      <div className={cx("flex flex-col gap-3 rounded-[22px] p-4", g.estado === "por_vencer" ? "bg-warn-soft" : "bg-surface")}>
        <p className={cx("display text-[26px] leading-tight font-bold", g.estado === "por_vencer" && "text-warn-ink")}>{cuandoVence(g)}</p>
        {g.estado === "en_reparacion" && g.en_reparacion_desde && (
          <p className="-mt-2 text-sm text-muted">Está en el service desde el {fechaCorta(g.en_reparacion_desde)}. Cuando vuelva, le sumo esos días.</p>
        )}
        <BarraGarantia g={g} />
      </div>

      <dl className="grid grid-cols-2 gap-2.5 text-sm">
        <div className="rounded-2xl bg-surface p-3">
          <dt className="text-muted">Garantía</dt>
          <dd className="font-bold">
            {duracion(g.meses)}
            {g.dias_reparacion > 0 && <span className="font-semibold text-muted"> + {g.dias_reparacion} días de service</span>}
          </dd>
        </div>
        {g.monto && (
          <div className="rounded-2xl bg-surface p-3">
            <dt className="text-muted">Pagaste</dt>
            <dd className="num font-bold">{monto(g.monto)}{g.medio_pago && <span className="font-semibold text-muted"> · {g.medio_pago}</span>}</dd>
          </div>
        )}
        {g.serie && (
          <div className="col-span-2 rounded-2xl bg-surface p-3">
            <dt className="text-muted">Número de serie</dt>
            <dd className="num font-bold tracking-wide select-all">{g.serie}</dd>
          </div>
        )}
        {g.notas && (
          <div className="col-span-2 rounded-2xl bg-surface p-3">
            <dt className="text-muted">Notas</dt>
            <dd className="font-semibold">{g.notas}</dd>
          </div>
        )}
      </dl>

      <div className="flex flex-col gap-2">
        <span className="text-[13px] font-bold">Comprobantes</span>
        {g.archivos.length > 0 && (
          <div className="flex gap-2.5 overflow-x-auto pb-1">
            {g.archivos.map((a) => (
              <a key={a.id} href={api.urlArchivo(a.id)} target="_blank" rel="noreferrer" className="press flex w-24 shrink-0 flex-col gap-1">
                <span className="flex h-28 items-center justify-center overflow-hidden rounded-2xl bg-surface-2">
                  {a.mime.startsWith("image/") ? <img src={api.urlArchivo(a.id)} alt="" className="h-full w-full object-cover" /> : <FileText size={28} className="text-faint" />}
                </span>
                <span className="truncate text-xs font-semibold text-muted">{ROL[a.rol] ?? a.nombre}</span>
              </a>
            ))}
          </div>
        )}
        {!g.archivos.length && <p className="text-sm text-muted">Sin la factura, reclamar es mucho más difícil. Sacale una foto ahora.</p>}
        <AdjuntarBoton texto={g.archivos.length ? "Agregar otro" : "Agregar factura o certificado"} onArchivo={subir} className="w-fit" />
      </div>

      {reclamar && (
        <div className="flex flex-col gap-2 rounded-[22px] border border-line-strong p-4 text-sm">
          <p className="font-bold">Si tenés que reclamar</p>
          <ol className="flex list-decimal flex-col gap-1.5 pl-5 text-muted">
            <li>Llevá la factura y, si tenés, el certificado de garantía.</li>
            <li>Podés reclamarle al comercio o al fabricante: responden los dos.</li>
            <li>Pedí constancia escrita de cuándo lo dejás y cuándo te lo devuelven. Ese tiempo se suma a la garantía.</li>
            <li>Si no te responden, hacé la denuncia en Defensa del Consumidor.</li>
          </ol>
        </div>
      )}

      <div className="flex flex-col gap-2">
        {g.estado === "en_reparacion" ? (
          <Boton variante="acento" disabled={ocupado} onClick={() => reparacion("volvio")}>Ya volvió del service</Boton>
        ) : (
          g.estado !== "vencida" && (
            <Boton variante="linea" disabled={ocupado} onClick={() => reparacion("enviar")}>
              <Wrench size={17} /> Lo mandé a reparar
            </Boton>
          )
        )}
        <div className="flex flex-wrap gap-x-5 gap-y-2 pt-1 text-sm">
          {g.movimiento_id && (
            <button className="font-bold text-accent" onClick={() => { onCerrar(); abrirMovimiento(g.movimiento_id!); }}>Ver el gasto</button>
          )}
          <button className="font-bold text-muted" onClick={() => setEditando(true)}>Editar</button>
          <button
            className="font-bold text-danger"
            onClick={async () => {
              await api.del(`/garantias/${g.id}`);
              refrescar();
              aviso(`Garantía borrada: ${g.producto}`);
              onCerrar();
            }}
          >
            Borrar
          </button>
        </div>
      </div>
    </div>
  );
}

function Formulario({ movimientoId, existente, onListo }: { movimientoId?: string; existente?: Garantia; onListo: () => void }) {
  const { aviso, refrescar } = useApp();
  const { data: mov } = useSWR<Movimiento>(movimientoId ? `/movimientos/${movimientoId}` : null);
  const [producto, setProducto] = useState(existente?.producto ?? "");
  const [fecha, setFecha] = useState(existente?.fecha_compra ?? hoyISO());
  const [meses, setMeses] = useState(existente?.meses ?? 12);
  const [otra, setOtra] = useState(existente ? !DURACIONES.some((d) => d.meses === existente.meses) : false);
  const [comercio, setComercio] = useState(existente?.comercio ?? "");
  const [serie, setSerie] = useState(existente?.serie ?? "");
  const [notas, setNotas] = useState(existente?.notas ?? "");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    if (mov && !producto) {
      setProducto(mov.descripcion.replace(/\s*\(\d+ cuotas\)$/, ""));
      setFecha(mov.fecha);
    }
  }, [mov]); // eslint-disable-line react-hooks/exhaustive-deps

  async function guardar() {
    setOcupado(true);
    setError(null);
    try {
      const datos = { producto: producto.trim(), fecha_compra: fecha, meses, comercio: comercio.trim(), serie: serie.trim(), notas: notas.trim() };
      let g: Garantia;
      if (existente) {
        g = await api.patch<Garantia>(`/garantias/${existente.id}`, datos);
      } else {
        g = await api.post<Garantia>("/garantias", { ...datos, movimiento_id: movimientoId });
        if (archivo) {
          if (movimientoId) await api.subir(`/movimientos/${movimientoId}/adjuntos/subir`, archivo, { rol: "garantia" });
          else {
            const a = await api.subir<{ id: string }>("/archivos", archivo);
            await api.patch(`/garantias/${g.id}`, { archivo_id: a.id });
          }
        }
      }
      vibrar();
      refrescar();
      aviso(existente ? "Garantía actualizada" : `${g.producto}: te aviso un mes antes de que venza`);
      onListo();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No pude conectar con el servidor");
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {mov && (
        <div className="flex items-center justify-between rounded-2xl bg-surface px-4 py-3 text-sm">
          <span className="text-muted">Compra del {fechaCorta(mov.fecha)}</span>
          <span className="num font-bold">{monto(mov.monto, mov.moneda)}</span>
        </div>
      )}
      <Campo label="Qué es">
        <input className={inputCls} value={producto} onChange={(e) => setProducto(e.target.value)} placeholder="Heladera, notebook, aire…" autoFocus={!movimientoId} />
      </Campo>
      <div className="flex flex-col gap-2">
        <span className="text-[13px] font-bold">Cuánto dura la garantía</span>
        <div className="flex flex-wrap gap-1.5">
          {DURACIONES.map((d) => (
            <Chip key={d.meses} activo={!otra && meses === d.meses} onClick={() => { setOtra(false); setMeses(d.meses); }}>{d.label}</Chip>
          ))}
          <Chip activo={otra} onClick={() => setOtra(true)}>Otra</Chip>
        </div>
        {otra && (
          <label className="flex items-center gap-2 text-sm font-semibold">
            <input className={inputCls + " num w-24"} inputMode="numeric" value={meses} onChange={(e) => setMeses(Math.max(1, Math.min(240, Number(e.target.value.replace(/\D/g, "")) || 1)))} />
            meses
          </label>
        )}
        <span className="text-xs text-faint">Si no sabés, fijate en la caja o la factura. Por ley, lo nuevo tiene como mínimo 6 meses.</span>
      </div>
      {!mov && (
        <Campo label="Cuándo lo compraste">
          <input type="date" className={inputCls} value={fecha} max={hoyISO()} onChange={(e) => e.target.value && setFecha(e.target.value)} />
        </Campo>
      )}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Campo label="Dónde (opcional)">
          <input className={inputCls} value={comercio} onChange={(e) => setComercio(e.target.value)} placeholder="Frávega, Mercado Libre…" />
        </Campo>
        <Campo label="Número de serie (opcional)">
          <input className={inputCls} value={serie} onChange={(e) => setSerie(e.target.value)} placeholder="Está en la etiqueta" />
        </Campo>
      </div>
      {existente && (
        <Campo label="Notas">
          <input className={inputCls} value={notas} onChange={(e) => setNotas(e.target.value)} />
        </Campo>
      )}
      {!existente && (
        <div className="flex items-center gap-3">
          <AdjuntarBoton texto={archivo ? "Cambiar foto" : "Foto de la factura o el certificado"} onArchivo={setArchivo} />
          {archivo && <span className="truncate text-sm text-muted">{archivo.name}</span>}
        </div>
      )}
      {error && <Mensaje>{error}</Mensaje>}
      <Boton variante="acento" disabled={ocupado || !producto.trim()} onClick={guardar}>
        {existente ? "Guardar cambios" : "Guardar garantía"}
      </Boton>
    </div>
  );
}
