"use client";

import { useEffect, useState } from "react";
import useSWR, { useSWRConfig } from "swr";
import { ArrowLeftRight, ChevronRight, ExternalLink, ShieldPlus, Trash2, X } from "lucide-react";
import { api, ApiError, type MedioPago, type Movimiento } from "@/lib/api";
import { monto } from "@/lib/format";
import { vibrar } from "@/lib/hooks";
import { AdjuntarBoton } from "./AdjuntarBoton";
import { EscudoGarantia, cuandoVence } from "./Garantias";
import { CategoriaPicker, FechaChips, MedioChips } from "./Selectores";
import { Sheet } from "./Sheet";
import { useApp } from "./Shell";
import { Boton, Campo, Chip, IconoCat, Mensaje, inputCls } from "./ui";

export function MovimientoSheet({ id, onCerrar }: { id: string | null; onCerrar: () => void }) {
  const { aviso, refrescar, abrirGarantia } = useApp();
  const { mutate: mutarTodo } = useSWRConfig();
  const { data: mov, mutate } = useSWR<Movimiento>(id ? `/movimientos/${id}` : null);

  const [desc, setDesc] = useState("");
  const [valor, setValor] = useState("");
  const [fecha, setFecha] = useState("");
  const [categoria, setCategoria] = useState<string | null>(null);
  const [medio, setMedio] = useState<string | null>(null);
  const [cuotas, setCuotas] = useState<number | null>(null);
  const { data: medios } = useSWR<MedioPago[]>(id ? "/medios-pago" : null);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    if (!mov) return;
    setDesc(mov.descripcion);
    setValor(mov.monto);
    setFecha(mov.fecha);
    setCategoria(mov.categoria_id);
    setMedio(mov.medio_pago_id);
    setCuotas(mov.cuotas);
    setError(null);
  }, [mov]);

  if (!id) return null;

  const cambios: Record<string, unknown> = {};
  if (mov) {
    if (desc !== mov.descripcion) cambios.descripcion = desc;
    if (Number(valor) !== Number(mov.monto)) cambios.monto = valor;
    if (fecha !== mov.fecha) cambios.fecha = fecha;
    if (categoria !== mov.categoria_id) cambios.categoria_id = categoria;
    if (medio !== mov.medio_pago_id) cambios.medio_pago_id = medio;
    if ((cuotas ?? 1) !== (mov.cuotas ?? 1)) cambios.cuotas = cuotas ?? 1;
  }
  const enCuotas = (cuotas ?? 1) > 1;
  const medioActual = medios?.find((m) => m.id === medio);
  const cuotasSinTarjeta = enCuotas && !!medioActual && medioActual.tipo !== "credito";
  const hayCambios = Object.keys(cambios).length > 0;

  async function correr(fn: () => Promise<unknown>, ok?: string) {
    setOcupado(true);
    setError(null);
    try {
      await fn();
      await mutate();
      refrescar();
      if (ok) aviso(ok);
      return true;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No pude conectar con el servidor");
      return false;
    } finally {
      setOcupado(false);
    }
  }

  function borrar() {
    if (!mov) return;
    const movId = mov.id;
    // Lo saco de las listas ya, y lo borro de verdad a los 5 s salvo «Deshacer».
    mutarTodo(
      (k) => typeof k === "string" && k.startsWith("/movimientos?"),
      (data: Movimiento[] | undefined) => (Array.isArray(data) ? data.filter((m) => m.id !== movId) : data),
      { revalidate: false }
    );
    const t = window.setTimeout(async () => {
      try {
        await api.del(`/movimientos/${movId}`);
      } finally {
        refrescar();
      }
    }, 5000);
    vibrar(20);
    aviso(`Borrado: ${mov.descripcion}`, { deshacer: () => window.clearTimeout(t) });
    onCerrar();
  }

  const esTransfer = mov?.tipo === "transferencia";
  const ingreso = mov?.tipo === "ingreso";

  return (
    <Sheet abierto={!!id} onCerrar={onCerrar}>
      {!mov ? (
        <div className="flex flex-col gap-3">
          <div className="esqueleto h-14" />
          <div className="esqueleto h-40" />
        </div>
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex items-center gap-3">
            {esTransfer ? (
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-surface-2 text-muted"><ArrowLeftRight size={22} /></span>
            ) : (
              <IconoCat icono={mov.categoria_icono} color={mov.categoria_color} size={48} />
            )}
            <div className="flex min-w-0 flex-1 flex-col">
              <span className="text-xs font-semibold text-muted">
                {mov.estado === "pendiente" ? "En la bandeja" : esTransfer ? "Transferencia" : (mov.categoria ?? "Sin categoría")}
              </span>
              <h2 className="truncate text-xl font-extrabold">{mov.descripcion}</h2>
            </div>
            <span className={`display num text-[28px] font-bold ${ingreso ? "text-ok" : ""}`}>
              {monto(mov.monto, mov.moneda, ingreso ? "+" : mov.tipo === "gasto" ? "-" : undefined)}
            </span>
          </div>

          {mov.texto_original && <p className="-mt-2 text-sm text-faint">Lo cargaste como «{mov.texto_original}»</p>}

          <div className="grid grid-cols-[1fr_9rem] gap-3">
            <Campo label="Descripción">
              <input className={inputCls} value={desc} onChange={(e) => setDesc(e.target.value)} />
            </Campo>
            <Campo label={`Monto en ${mov.moneda === "USD" ? "dólares" : "pesos"}`}>
              <input className={inputCls + " num"} inputMode="decimal" value={valor} onChange={(e) => setValor(e.target.value.replace(",", "."))} />
            </Campo>
          </div>

          <div className="flex flex-col gap-2">
            <span className="text-[13px] font-bold">Cuándo</span>
            <FechaChips valor={fecha} onCambio={setFecha} />
          </div>

          {!esTransfer && (
            <div className="flex flex-col gap-2">
              <span className="text-[13px] font-bold">Categoría</span>
              <CategoriaPicker valor={categoria} tipo={ingreso ? "ingreso" : "gasto"} onCambio={setCategoria} />
            </div>
          )}

          {esTransfer ? (
            <p className="rounded-2xl bg-surface p-4 text-sm">
              De <b>{mov.cuenta}</b> a <b>{mov.cuenta_destino}</b>
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              <span className="text-[13px] font-bold">{ingreso ? "Entró en" : "Pagaste con"}</span>
              {cuotasSinTarjeta && (
                <Mensaje>Es en cuotas pero está cargada con {medioActual?.nombre}: elegí la tarjeta con la que la pagás (o dejala en un pago).</Mensaje>
              )}
              <MedioChips valor={medio} onCambio={setMedio} soloCredito={enCuotas && !ingreso} />
            </div>
          )}

          {mov.tipo === "gasto" && !mov.deuda_id && (
            <div className="flex flex-col gap-2">
              <span className="text-[13px] font-bold">Cuotas</span>
              <div className="flex flex-wrap gap-1.5">
                {[...new Set([1, 3, 6, 12, 18, cuotas ?? 1])].sort((a, b) => a - b).map((k) => (
                  <Chip key={k} activo={(cuotas ?? 1) === k} onClick={() => setCuotas(k === 1 ? null : k)}>{k === 1 ? "Un pago" : k}</Chip>
                ))}
              </div>
            </div>
          )}

          <div className="flex flex-col gap-2">
            <span className="text-[13px] font-bold">Comprobantes</span>
            {mov.adjuntos.map((a) => (
              <div key={a.archivo_id} className="flex items-center gap-3 rounded-2xl bg-surface p-2">
                {a.mime.startsWith("image/") ? (
                  <img src={api.urlArchivo(a.archivo_id)} alt="" className="h-12 w-12 rounded-xl object-cover" />
                ) : (
                  <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-surface-2 text-[11px] font-extrabold text-muted">PDF</span>
                )}
                <a href={api.urlArchivo(a.archivo_id)} target="_blank" rel="noreferrer" className="flex min-w-0 flex-1 items-center gap-1.5 text-sm font-bold">
                  <span className="truncate">{a.nombre}</span>
                  <ExternalLink size={14} className="shrink-0 text-faint" />
                </a>
                <button
                  aria-label={`Desvincular ${a.nombre}`}
                  className="press flex h-11 w-11 items-center justify-center rounded-xl text-faint hover:text-ink"
                  onClick={() => correr(() => api.del(`/movimientos/${mov.id}/adjuntos/${a.archivo_id}`), "Comprobante desvinculado")}
                >
                  <X size={18} />
                </button>
              </div>
            ))}
            <AdjuntarBoton
              texto={mov.adjuntos.length ? "Adjuntar otro" : "Adjuntar comprobante"}
              onArchivo={(f) => correr(() => api.subir(`/movimientos/${mov.id}/adjuntos/subir`, f, { rol: "ticket" }), "Comprobante guardado")}
            />
          </div>

          {mov.tipo === "gasto" && !mov.deuda_id && (
            mov.garantia ? (
              <button
                onClick={() => { onCerrar(); abrirGarantia({ id: mov.garantia!.id }); }}
                className="press flex items-center gap-3 rounded-2xl bg-surface p-3 text-left"
              >
                <EscudoGarantia estado={mov.garantia.estado} size={40} />
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="text-sm font-bold">Garantía</span>
                  <span className="text-[13px] text-muted">{cuandoVence(mov.garantia)}</span>
                </span>
                <ChevronRight size={18} className="text-faint" />
              </button>
            ) : (
              <button
                onClick={() => { onCerrar(); abrirGarantia({ nueva: true, movimiento: mov.id }); }}
                className="press flex w-fit items-center gap-1.5 text-sm font-bold text-accent"
              >
                <ShieldPlus size={17} /> ¿Tiene garantía? Anotala
              </button>
            )
          )}

          {error && <Mensaje>{error}</Mensaje>}

          <div className="flex gap-2">
            <Boton variante="peligro" aria-label="Borrar movimiento" disabled={ocupado} onClick={borrar}>
              <Trash2 size={18} />
            </Boton>
            {mov.estado === "pendiente" ? (
              <Boton
                variante="acento"
                className="flex-1"
                disabled={ocupado}
                onClick={async () => {
                  const ok = await correr(async () => {
                    if (hayCambios) await api.patch(`/movimientos/${mov.id}`, cambios);
                    await api.post(`/movimientos/${mov.id}/confirmar`);
                  }, "Confirmado");
                  if (ok) {
                    vibrar();
                    onCerrar();
                  }
                }}
              >
                Confirmar
              </Boton>
            ) : hayCambios ? (
              <Boton
                variante="acento"
                className="flex-1"
                disabled={ocupado}
                onClick={async () => {
                  if (await correr(() => api.patch(`/movimientos/${mov.id}`, cambios), "Cambios guardados")) onCerrar();
                }}
              >
                Guardar cambios
              </Boton>
            ) : (
              <Boton variante="linea" className="flex-1" onClick={onCerrar}>
                Listo
              </Boton>
            )}
          </div>
        </div>
      )}
    </Sheet>
  );
}
