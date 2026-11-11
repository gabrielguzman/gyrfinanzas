"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { Check, Plus, Repeat, Sparkles } from "lucide-react";
import { CategoriaPicker, MedioChips } from "@/components/Selectores";
import { Sheet } from "@/components/Sheet";
import { useApp } from "@/components/Shell";
import { Boton, Campo, Esqueleto, IconoCat, Lista, Mensaje, Seccion, Titulo, Vacio, cx, inputCls } from "@/components/ui";
import { api, ApiError, type Fijo, type Fijos, type FijoSugerido } from "@/lib/api";
import { fechaCorta, monto } from "@/lib/format";
import { useContador, vibrar } from "@/lib/hooks";

const pesos = (v: string | number) => monto(Math.round(Number(v)));

function Estado({ f, onAbrirMov }: { f: Fijo; onAbrirMov: (id: string) => void }) {
  if (f.este_mes === "pagado")
    return <span className="flex items-center gap-1 rounded-full bg-ok-soft px-2 py-0.5 text-[11px] font-bold text-ok"><Check size={12} strokeWidth={3} /> Pagado</span>;
  if (f.este_mes === "en_bandeja")
    return (
      <span
        role="button"
        tabIndex={0}
        onClick={(e) => { e.stopPropagation(); if (f.movimiento_id) onAbrirMov(f.movimiento_id); }}
        className="rounded-full bg-warn-soft px-2 py-0.5 text-[11px] font-bold text-warn-ink"
      >
        Para confirmar
      </span>
    );
  return <span className="text-[12px] font-semibold text-faint">el {fechaCorta(f.proxima)}</span>;
}

function Sugerencias({ sug, onListo }: { sug: FijoSugerido[]; onListo: () => void }) {
  const { aviso } = useApp();
  const [ocupado, setOcupado] = useState<string | null>(null);
  async function decidir(s: FijoSugerido[], activo: boolean) {
    setOcupado(s.length > 1 ? "todos" : s[0].clave);
    try {
      for (const x of s) await api.post("/fijos/decidir", { clave: x.clave, activo });
      vibrar();
      aviso(activo ? (s.length > 1 ? `Activé ${s.length} gastos fijos` : `${s[0].nombre}: activado`) : `Listo, ${s[0].nombre} no es fijo`);
      onListo();
    } catch (e) {
      aviso(e instanceof ApiError ? e.message : "No pude conectar con el servidor");
    } finally {
      setOcupado(null);
    }
  }
  return (
    <section className="flex flex-col gap-4 rounded-[24px] border-2 border-dashed border-accent/40 bg-accent-soft/50 p-5">
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[14px] bg-accent text-accent-ink"><Sparkles size={19} /></span>
        <div className="flex flex-1 flex-col gap-0.5">
          <h2 className="font-extrabold">{sug.length === 1 ? "Esto parece un gasto fijo" : `Estos ${sug.length} parecen gastos fijos`}</h2>
          <p className="text-sm text-muted">Se repiten cada mes en tus movimientos. Activalos y el día que tocan aparecen en la bandeja para confirmar con un toque.</p>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        {sug.map((s) => (
          <div key={s.clave} className="flex flex-col gap-3 rounded-2xl bg-surface p-3.5 shadow-soft sm:flex-row sm:items-center">
            <div className="flex min-w-0 flex-1 flex-col">
              <span className="truncate font-bold">{s.nombre}</span>
              <span className="text-[13px] text-muted">
                <b className="num text-ink">{pesos(s.monto)}</b> · el {s.dia} de cada mes · {s.meses} meses seguidos
              </span>
            </div>
            <div className="grid grid-cols-2 gap-1.5 sm:flex">
              <Boton variante="linea" className="min-h-10 px-3" disabled={!!ocupado} onClick={() => decidir([s], false)}>No es fijo</Boton>
              <Boton variante="acento" className="min-h-10 px-3" disabled={!!ocupado} onClick={() => decidir([s], true)}>Activar</Boton>
            </div>
          </div>
        ))}
      </div>
      {sug.length > 1 && (
        <Boton variante="primario" disabled={!!ocupado} onClick={() => decidir(sug, true)}>
          <Check size={18} /> Activar los {sug.length}
        </Boton>
      )}
    </section>
  );
}

type Abierto = { nuevo: true } | { fijo: Fijo } | null;

function FijoSheet({ abierto, onCerrar }: { abierto: Abierto; onCerrar: () => void }) {
  const { aviso, refrescar } = useApp();
  const f = abierto && "fijo" in abierto ? abierto.fijo : null;
  const [nombre, setNombre] = useState("");
  const [valor, setValor] = useState("");
  const [dia, setDia] = useState("");
  const [categoria, setCategoria] = useState<string | null>(null);
  const [medio, setMedio] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    if (!abierto) return;
    setNombre(f?.nombre ?? "");
    setValor(f ? String(Math.round(Number(f.monto))) : "");
    setDia(f ? String(f.dia) : String(new Date().getDate()));
    setCategoria(f?.categoria_id ?? null);
    setMedio(f?.medio_pago_id ?? null);
    setError(null);
  }, [abierto, f]);

  async function correr(fn: () => Promise<unknown>, ok: string) {
    setOcupado(true);
    setError(null);
    try {
      await fn();
      refrescar();
      aviso(ok);
      onCerrar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No pude conectar con el servidor");
    } finally {
      setOcupado(false);
    }
  }

  const datos = { nombre: nombre.trim(), monto: valor, dia: Number(dia), categoria_id: categoria, medio_pago_id: medio };
  const valido = datos.nombre && Number(valor) > 0 && datos.dia >= 1 && datos.dia <= 31;

  return (
    <Sheet abierto={!!abierto} onCerrar={onCerrar} titulo={f ? f.nombre : "Nuevo gasto fijo"}>
      <Campo label="Qué es">
        <input className={inputCls} value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Alquiler, internet, Netflix…" />
      </Campo>
      <div className="grid grid-cols-[1fr_110px] gap-3">
        <Campo label="Cuánto" ayuda="Se propone el último que pagaste">
          <input className={cx(inputCls, "num")} inputMode="decimal" value={valor} onChange={(e) => setValor(e.target.value.replace(/[^\d.,]/g, "").replace(",", "."))} placeholder="0" />
        </Campo>
        <Campo label="Día del mes">
          <input className={cx(inputCls, "num")} inputMode="numeric" value={dia} onChange={(e) => setDia(e.target.value.replace(/\D/g, "").slice(0, 2))} />
        </Campo>
      </div>
      <Campo label="Categoría">
        <CategoriaPicker valor={categoria} tipo="gasto" onCambio={setCategoria} />
      </Campo>
      <Campo label="Con qué lo pagás">
        <MedioChips valor={medio} onCambio={setMedio} />
      </Campo>
      {error && <Mensaje tono="error">{error}</Mensaje>}
      <Boton variante="acento" disabled={!valido || ocupado}
        onClick={() => correr(() => (f ? api.patch(`/fijos/${f.id}`, datos) : api.post("/fijos", datos)), f ? "Cambios guardados" : `${datos.nombre}: listo`)}>
        {f ? "Guardar" : "Crear gasto fijo"}
      </Boton>
      {f && (
        <div className="grid grid-cols-2 gap-2">
          <Boton variante="linea" disabled={ocupado || f.este_mes === "pagado"} onClick={() => correr(() => api.post(`/fijos/${f.id}/saltear`), "Este mes no va")}>
            Este mes no va
          </Boton>
          <Boton variante="peligro" disabled={ocupado} onClick={() => correr(() => api.del(`/fijos/${f.id}`), `${f.nombre} ya no es fijo`)}>
            Ya no es fijo
          </Boton>
        </div>
      )}
    </Sheet>
  );
}

export default function FijosPage() {
  const { data, mutate } = useSWR<Fijos>("/fijos");
  const { abrirMovimiento } = useApp();
  const [abierto, setAbierto] = useState<Abierto>(null);
  const total = useContador(Number(data?.total_mensual ?? 0));

  if (!data) return <Esqueleto className="h-96 rounded-[28px]" />;
  const activos = data.fijos.filter((f) => f.activo).sort((a, b) => a.proxima.localeCompare(b.proxima));
  const descartados = data.fijos.filter((f) => !f.activo);
  const pagado = Number(data.pagado_mes), tot = Number(data.total_mensual);
  const proximo = activos.find((f) => f.este_mes === "por_venir");

  return (
    <div className="flex flex-col gap-7 lg:max-w-3xl">
      <Titulo extra={<Boton variante="linea" onClick={() => setAbierto({ nuevo: true })}><Plus size={18} /> Nuevo</Boton>}>Gastos fijos</Titulo>

      {activos.length > 0 && (
        <section className="flex flex-col gap-4 rounded-[28px] bg-surface p-6 shadow-soft">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div className="flex flex-col gap-1">
              <span className="text-sm font-semibold text-muted">Por mes pagás</span>
              <span className="display num text-[40px] leading-none font-bold">{pesos(total)}</span>
            </div>
            {proximo && (
              <span className="text-sm text-muted">
                Próximo: <b className="text-ink">{proximo.nombre}</b> el {fechaCorta(proximo.proxima)}
              </span>
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            <div className="h-2.5 overflow-hidden rounded-full bg-surface-2">
              <div className="suave h-full rounded-full bg-ok" style={{ width: `${tot ? Math.min(100, (pagado / tot) * 100) : 0}%` }} />
            </div>
            <span className="text-[13px] text-muted">
              Este mes ya pagaste <b className="num text-ink">{pesos(pagado)}</b>{pagado < tot && <>; faltan <b className="num text-ink">{pesos(tot - pagado)}</b></>}.
            </span>
          </div>
        </section>
      )}

      {data.sugeridos.length > 0 && <Sugerencias sug={data.sugeridos} onListo={() => mutate()} />}

      {activos.length > 0 ? (
        <Seccion titulo="Tus fijos">
          <Lista>
            {activos.map((f) => (
              <button key={f.id} onClick={() => setAbierto({ fijo: f })} className="press flex min-h-[64px] w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-surface-2">
                <IconoCat icono={f.categoria_icono} color={f.categoria_color} />
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="truncate text-[15px] font-bold">{f.nombre}</span>
                  <span className="truncate text-[13px] text-muted">El {f.dia} de cada mes{f.medio_pago && ` · ${f.medio_pago}`}</span>
                </span>
                <span className="flex shrink-0 flex-col items-end gap-1">
                  <span className="num text-[15px] font-extrabold">{pesos(f.monto)}</span>
                  <Estado f={f} onAbrirMov={abrirMovimiento} />
                </span>
              </button>
            ))}
          </Lista>
          <p className="flex items-start gap-2 text-[13px] text-muted">
            <Repeat size={15} className="mt-0.5 shrink-0" />
            El día que toca, cada uno aparece en la bandeja con el último monto. Si cambió, lo corregís al confirmar y el mes que viene propone el nuevo.
          </p>
        </Seccion>
      ) : (
        data.sugeridos.length === 0 && (
          <Vacio titulo="Todavía no hay gastos fijos" accion={<Boton variante="acento" onClick={() => setAbierto({ nuevo: true })}><Plus size={18} /> Cargar el primero</Boton>}>
            Alquiler, expensas, internet, el gimnasio, Netflix. Cuando algo se repite dos meses en tus movimientos, te lo sugiero acá solo.
          </Vacio>
        )
      )}

      {descartados.length > 0 && (
        <Seccion titulo="No son fijos">
          <p className="-mt-1 text-[13px] text-muted">No los cuento en el plan ni te los vuelvo a sugerir.</p>
          <div className="flex flex-wrap gap-1.5">
            {descartados.map((f) => (
              <button key={f.id} onClick={async () => { await api.patch(`/fijos/${f.id}`, { activo: true }); mutate(); }}
                className="press flex min-h-10 items-center gap-1.5 rounded-full border border-line-strong bg-surface px-3.5 text-[13px] font-bold">
                {f.nombre} <span className="text-accent">· Activar</span>
              </button>
            ))}
          </div>
        </Seccion>
      )}

      <FijoSheet abierto={abierto} onCerrar={() => setAbierto(null)} />
    </div>
  );
}
