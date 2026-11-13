"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { ArrowRight, Bell, Shapes, BellOff, Send, Tags, X } from "lucide-react";
import { ExportarPanel } from "@/components/Exportar";
import { CategoriaPicker } from "@/components/Selectores";
import { useApp } from "@/components/Shell";
import { Boton, Esqueleto, IconoCat, Lista, Mensaje, Seccion, Titulo, cx, inputCls } from "@/components/ui";
import { api, ApiError, type Categoria, type EstadoAvisos, type PrefsAvisos, type PreviaRegla, type Regla } from "@/lib/api";
import { activar, desactivar, soporte, suscripcionActual, type Soporte } from "@/lib/push";

const PREFS: { k: keyof Omit<PrefsAvisos, "notif_hora">; titulo: string; detalle: string }[] = [
  { k: "notif_hoy", titulo: "Cuánto podés gastar hoy", detalle: "Todas las mañanas, a la hora que elijas" },
  { k: "notif_fijos", titulo: "Gastos fijos", detalle: "El día que toca el alquiler, internet o una suscripción" },
  { k: "notif_vencimientos", titulo: "Vencimientos", detalle: "El día antes y el día que vence una tarjeta o un préstamo" },
  { k: "notif_avisos", titulo: "Avisos importantes", detalle: "Garantías por vencer, fijos sin confirmar, patente o seguro que se viene" },
  { k: "notif_racha", titulo: "Recordatorio de la noche", detalle: "A las 21, si ese día todavía no cargaste nada" },
];

function Interruptor({ activo, onCambio, label }: { activo: boolean; onCambio: (v: boolean) => void; label: string }) {
  return (
    <button role="switch" aria-checked={activo} aria-label={label} onClick={() => onCambio(!activo)}
      className={cx("press relative h-7 w-12 shrink-0 rounded-full transition-colors", activo ? "bg-accent" : "bg-line-strong")}>
      <span className={cx("absolute top-1 left-1 h-5 w-5 rounded-full bg-white shadow transition-transform", activo && "translate-x-5")} />
    </button>
  );
}

function Avisos() {
  const { aviso } = useApp();
  const { data, mutate } = useSWR<EstadoAvisos>("/avisos");
  const [sop, setSop] = useState<Soporte | null>(null);
  const [aca, setAca] = useState<boolean | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const s = soporte();
    setSop(s);
    if (s === "ok") suscripcionActual().then((x) => setAca(!!x)).catch(() => setAca(false));
    else setAca(false);
  }, []);

  async function correr(fn: () => Promise<unknown>) {
    setOcupado(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof ApiError || e instanceof Error ? e.message : "No pude activar las notificaciones");
    } finally {
      setOcupado(false);
    }
  }

  async function pref(cambio: Partial<PrefsAvisos>) {
    if (!data) return;
    mutate({ ...data, preferencias: { ...data.preferencias, ...cambio } }, { revalidate: false });
    try {
      mutate(await api.put<EstadoAvisos>("/avisos/preferencias", cambio), { revalidate: false });
    } catch {
      mutate();
    }
  }

  if (!data || sop === null || aca === null) return <Esqueleto className="h-64 rounded-[22px]" />;
  const otros = data.dispositivos - (aca ? 1 : 0);

  return (
    <Seccion titulo="Notificaciones en el celu">
      <div className="flex flex-col gap-4 rounded-[22px] bg-surface p-5 shadow-soft">
        <div className="flex items-start gap-3">
          <span className={cx("flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px]", aca ? "bg-ok-soft text-ok" : "bg-surface-2 text-muted")}>
            {aca ? <Bell size={20} /> : <BellOff size={20} />}
          </span>
          <div className="flex flex-1 flex-col gap-0.5">
            <b>{aca ? "Activadas en este dispositivo" : "Desactivadas en este dispositivo"}</b>
            <span className="text-[13px] text-muted">
              {otros > 0 ? `También llegan a ${otros === 1 ? "otro dispositivo" : `${otros} dispositivos más`}.` : "Te llegan aunque tengas la app cerrada, sin Telegram."}
            </span>
          </div>
        </div>

        {sop === "ios_instalar" && (
          <Mensaje>En iPhone primero agregá la app a la pantalla de inicio (Compartir › «Agregar a inicio») y abrila desde ahí. Después activás las notificaciones acá.</Mensaje>
        )}
        {sop === "inseguro" && (
          <Mensaje>Las notificaciones necesitan una conexión segura (https). Activalas desde la app publicada, no desde la red de tu casa.</Mensaje>
        )}
        {sop === "no" && <Mensaje>Este navegador no soporta notificaciones.</Mensaje>}
        {error && <Mensaje tono="error">{error}</Mensaje>}

        {sop === "ok" && (
          <div className="flex flex-wrap gap-2">
            {aca ? (
              <>
                <Boton variante="linea" disabled={ocupado} onClick={() => correr(async () => {
                  const r = await api.post<{ enviadas: number }>("/avisos/probar", {});
                  aviso(r.enviadas ? "Te mandé una de prueba" : "No pude mandarla: probá desactivar y activar");
                })}><Send size={16} /> Mandar una de prueba</Boton>
                <Boton variante="fantasma" disabled={ocupado} onClick={() => correr(async () => {
                  const r = await desactivar();
                  if (r) mutate(r, { revalidate: false });
                  setAca(false);
                })}>Desactivar acá</Boton>
              </>
            ) : (
              <Boton variante="acento" disabled={ocupado} onClick={() => correr(async () => {
                mutate(await activar(data.clave_publica), { revalidate: false });
                setAca(true);
                aviso("¡Listo! Te van a llegar los avisos");
              })}><Bell size={17} /> Activar notificaciones</Boton>
            )}
          </div>
        )}
      </div>

      <Lista>
        {PREFS.map((p) => (
          <div key={p.k} className="flex items-center gap-3 px-4 py-3.5">
            <span className="flex min-w-0 flex-1 flex-col gap-0.5">
              <span className="text-[15px] font-bold">{p.titulo}</span>
              <span className="text-[13px] text-muted">{p.detalle}</span>
            </span>
            <Interruptor label={p.titulo} activo={data.preferencias[p.k]} onCambio={(v) => pref({ [p.k]: v })} />
          </div>
        ))}
        <label className="flex items-center gap-3 px-4 py-3.5">
          <span className="flex min-w-0 flex-1 flex-col gap-0.5">
            <span className="text-[15px] font-bold">Hora de los avisos</span>
            <span className="text-[13px] text-muted">Antes de esta hora (y después de las 22) no te molesto</span>
          </span>
          <input type="time" value={data.preferencias.notif_hora} onChange={(e) => e.target.value && pref({ notif_hora: e.target.value })}
            className="num min-h-11 rounded-xl border border-line-strong bg-surface px-3 font-bold" />
        </label>
      </Lista>
    </Seccion>
  );
}

function Reglas() {
  const { aviso, refrescar } = useApp();
  const { data: reglas, mutate } = useSWR<Regla[]>("/reglas");
  const { data: cats } = useSWR<Categoria[]>("/categorias");
  const [texto, setTexto] = useState("");
  const [categoria, setCategoria] = useState<string | null>(null);
  const [aplicar, setAplicar] = useState(true);
  const [previa, setPrevia] = useState<PreviaRegla | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const t = texto.trim();
    if (t.length < 2) return setPrevia(null);
    const id = window.setTimeout(() => {
      api.post<PreviaRegla>("/reglas/previa", { texto: t, categoria_id: categoria }).then(setPrevia).catch(() => setPrevia(null));
    }, 300);
    return () => window.clearTimeout(id);
  }, [texto, categoria]);

  const nombreCat = cats?.find((c) => c.id === categoria)?.nombre;

  async function crear() {
    if (!categoria) return;
    setError(null);
    try {
      const r = await api.post<{ cambiados: number }>("/reglas", { texto: texto.trim(), categoria_id: categoria, aplicar });
      aviso(r.cambiados ? `Regla creada: ${r.cambiados} recategorizados` : "Regla creada");
      setTexto("");
      setCategoria(null);
      setPrevia(null);
      mutate();
      refrescar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No pude conectar con el servidor");
    }
  }

  return (
    <Seccion titulo="Reglas de categorías">
      <p className="-mt-1 text-sm text-muted">
        Si la descripción dice tal cosa, va a tal categoría. Ganan sobre todo lo demás. También te las propongo cuando le cambiás la categoría a un gasto.
      </p>
      {reglas && reglas.length > 0 && (
        <Lista>
          {reglas.map((r) => (
            <div key={r.id} className="flex items-center gap-3 px-4 py-2.5">
              <span className="min-w-0 truncate rounded-lg bg-surface-2 px-2 py-1 font-mono text-[13px] font-bold">{r.texto}</span>
              <ArrowRight size={15} className="shrink-0 text-faint" />
              <IconoCat icono={r.categoria_icono} color={r.categoria_color} size={30} />
              <span className="min-w-0 flex-1 truncate text-[15px] font-bold">{r.categoria}</span>
              <button aria-label={`Borrar regla ${r.texto}`} onClick={async () => { await api.del(`/reglas/${r.id}`); mutate(); }}
                className="press flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-faint hover:bg-surface-2">
                <X size={16} />
              </button>
            </div>
          ))}
        </Lista>
      )}
      <div className="flex flex-col gap-3 rounded-[22px] bg-surface p-4 shadow-soft">
        <span className="flex items-center gap-2 text-sm font-bold"><Tags size={16} /> Nueva regla</span>
        <input className={inputCls} value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Si dice… (uber, farmacity, spotify)" />
        <CategoriaPicker valor={categoria} tipo="gasto" onCambio={setCategoria} />
        {previa && (
          <p className="text-[13px] text-muted">
            {previa.total === 0 ? (
              <>Todavía no hay movimientos que digan «{previa.texto}». Se aplica a lo que cargues desde ahora.</>
            ) : (
              <>
                Coincide con <b className="text-ink">{previa.total}</b> {previa.total === 1 ? "movimiento" : "movimientos"}
                {previa.ejemplos.length > 0 && <> ({previa.ejemplos.join(", ")})</>}
                {nombreCat && previa.a_cambiar > 0 && <>; <b className="text-ink">{previa.a_cambiar}</b> pasarían a {nombreCat}</>}.
              </>
            )}
          </p>
        )}
        {previa && previa.a_cambiar > 0 && (
          <label className="flex items-center gap-2.5 text-sm font-semibold">
            <input type="checkbox" checked={aplicar} onChange={(e) => setAplicar(e.target.checked)} className="h-5 w-5 accent-[var(--accent)]" />
            Cambiar también los que ya cargaste
          </label>
        )}
        {error && <Mensaje tono="error">{error}</Mensaje>}
        <Boton variante="acento" disabled={texto.trim().length < 2 || !categoria} onClick={crear}>Crear regla</Boton>
      </div>
    </Seccion>
  );
}

export default function AjustesPage() {
  return (
    <div className="flex flex-col gap-8 lg:max-w-3xl">
      <Titulo>Ajustes</Titulo>
      <Link href="/categorias" className="press flex items-center gap-3 rounded-[22px] bg-surface p-4 shadow-soft hover:bg-surface-2">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px] bg-accent-soft text-accent"><Shapes size={20} /></span>
        <span className="flex flex-1 flex-col">
          <b>Categorías</b>
          <span className="text-[13px] text-muted">Agregá las tuyas o las clásicas (Kiosco, Farmacia, Mascotas…), cambiales el ícono o fusionalas</span>
        </span>
        <ArrowRight size={18} className="text-faint" />
      </Link>
      <Avisos />
      <Reglas />
      <Seccion titulo="Exportar tus datos">
        <ExportarPanel />
      </Seccion>
    </div>
  );
}
