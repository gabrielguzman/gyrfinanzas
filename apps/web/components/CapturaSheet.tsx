"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import useSWR from "swr";
import { Camera, FileCheck2, Pencil } from "lucide-react";
import { api, ApiError, type Frecuente, type Interpretacion, type Movimiento, type Presupuesto } from "@/lib/api";
import { encolar } from "@/lib/cola";
import { hoyISO, monto } from "@/lib/format";
import { vibrar } from "@/lib/hooks";
import { CategoriaPicker, FechaChips, MedioChips } from "./Selectores";
import { Sheet } from "./Sheet";
import { duracion } from "./Garantias";
import { FueraDeSaldo, anteriorALaCuenta, useCuentaDe } from "./FueraDeSaldo";
import { useApp } from "./Shell";
import { Boton, IconoCat, Mensaje, cx } from "./ui";

const EJEMPLOS = ["nafta 40k visa", "café 2500 mp", "cobré el sueldo 1.45M", "heladera 850k garantía 1 año"];
const TIPO = { gasto: "Gasto", ingreso: "Ingreso", transferencia: "Transferencia" } as const;

/** El texto con lo reconocido resaltado, debajo de un textarea transparente. */
function Espejo({ texto, partes }: { texto: string; partes: Interpretacion["partes"] }) {
  const trozos: React.ReactNode[] = [];
  let i = 0;
  partes.forEach((p, k) => {
    if (p.inicio > i) trozos.push(texto.slice(i, p.inicio));
    trozos.push(<mark key={k} data-t={p.tipo}>{texto.slice(p.inicio, p.fin)}</mark>);
    i = p.fin;
  });
  trozos.push(texto.slice(i) + "​");
  return <div className="espejo pointer-events-none absolute inset-0 text-transparent" aria-hidden>{trozos}</div>;
}

export function CapturaSheet({ abierto, onCerrar }: { abierto: boolean; onCerrar: () => void }) {
  const { aviso, refrescar } = useApp();
  const { data: frecuentes } = useSWR<Frecuente[]>(abierto ? "/captura/frecuentes" : null);
  const [texto, setTexto] = useState("");
  const [vista, setVista] = useState<(Interpretacion & { para: string }) | null>(null);
  const [medio, setMedio] = useState<string | null>(null);
  const [categoria, setCategoria] = useState<string | null>(null);
  const [fecha, setFecha] = useState<string | null>(null);
  const [fuera, setFuera] = useState<boolean | null>(null);
  const [verCategorias, setVerCategorias] = useState(false);
  const [archivo, setArchivo] = useState<File | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fotoRef = useRef<HTMLInputElement>(null);
  const areaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (abierto) window.setTimeout(() => areaRef.current?.focus(), 280);
  }, [abierto]);

  useLayoutEffect(() => {
    const el = areaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [texto, abierto]);

  useEffect(() => {
    setError(null);
    if (texto.trim().length < 2) {
      setVista(null);
      return;
    }
    const para = texto;
    const t = window.setTimeout(async () => {
      try {
        const v = await api.post<Interpretacion>("/captura/previsualizar", { texto: para });
        setVista({ ...v, para });
      } catch {
        setVista(null);
      }
    }, 220);
    return () => window.clearTimeout(t);
  }, [texto]);

  const medioFinal = medio ?? vista?.medio_pago_id ?? null;
  const categoriaFinal = categoria ?? vista?.categoria_id ?? null;
  const fechaFinal = fecha ?? vista?.fecha ?? hoyISO();
  const cuentaMov = useCuentaDe(medioFinal);
  const sugerirFuera = anteriorALaCuenta(fechaFinal, cuentaMov);
  const fueraFinal = fuera ?? sugerirFuera;
  const partes = vista && vista.para === texto ? vista.partes : [];

  function reiniciar() {
    setTexto("");
    setVista(null);
    setMedio(null);
    setCategoria(null);
    setFecha(null);
    setFuera(null);
    setVerCategorias(false);
    setArchivo(null);
    setError(null);
  }

  async function guardar() {
    if (!texto.trim() || guardando) return;
    if (!navigator.onLine) {
      encolar(texto, medioFinal);
      aviso("Sin conexión: lo guardé y se envía cuando vuelva la red");
      reiniciar();
      onCerrar();
      return;
    }
    setGuardando(true);
    try {
      let mov = await api.post<Movimiento>("/captura", { texto });
      const cambios: Record<string, unknown> = {};
      if (medio && medio !== mov.medio_pago_id) cambios.medio_pago_id = medio;
      if (categoria && categoria !== mov.categoria_id) cambios.categoria_id = categoria;
      if (fecha && fecha !== mov.fecha) cambios.fecha = fecha;
      if (fueraFinal && mov.tipo !== "transferencia") cambios.fuera_de_saldo = true;
      if (Object.keys(cambios).length) mov = await api.patch<Movimiento>(`/movimientos/${mov.id}`, cambios);
      if (archivo) await api.subir(`/movimientos/${mov.id}/adjuntos/subir`, archivo, { rol: "ticket" });
      const id = mov.id;
      if (mov.medio_pago_id) {
        await api.post(`/movimientos/${id}/confirmar`);
        vibrar();
        let resto = "";
        if (mov.tipo === "gasto") {
          const p = await api.get<Presupuesto>("/plan").catch(() => null);
          if (p?.configurado) resto = Number(p.hoy) >= 0 ? ` · hoy te quedan ${monto(p.hoy)}` : ` · hoy te pasaste ${monto(-Number(p.hoy))}`;
        }
        aviso(`Guardado: ${mov.descripcion} ${monto(mov.monto, mov.moneda)}${resto}`, { deshacer: () => api.del(`/movimientos/${id}`) });
      } else {
        aviso("Quedó en la bandeja: falta con qué pagaste", { deshacer: () => api.del(`/movimientos/${id}`) });
      }
      refrescar();
      reiniciar();
      onCerrar();
    } catch (e) {
      if (e instanceof ApiError) setError(e.message);
      else {
        encolar(texto, medioFinal);
        aviso("No pude conectar: lo guardé y se envía después");
        reiniciar();
        onCerrar();
      }
    } finally {
      setGuardando(false);
    }
  }

  const ingreso = vista?.tipo === "ingreso";

  return (
    <Sheet abierto={abierto} onCerrar={onCerrar} titulo="¿Qué pasó?">
      <form
        className="flex flex-col gap-5"
        onSubmit={(e) => {
          e.preventDefault();
          guardar();
        }}
      >
        <div className="flex flex-col gap-2">
          <div className="relative rounded-[20px] border-2 border-accent bg-surface text-[18px] font-semibold">
            <Espejo texto={texto} partes={partes} />
            <textarea
              ref={areaRef}
              rows={1}
              value={texto}
              onChange={(e) => setTexto(e.target.value.replace(/\n/g, ""))}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  guardar();
                }
              }}
              placeholder="nafta 40k visa"
              aria-label="Escribí el gasto como te salga"
              autoComplete="off"
              enterKeyHint="done"
              className="espejo-input relative block w-full resize-none overflow-hidden bg-transparent text-ink caret-accent outline-none placeholder:text-faint"
            />
          </div>
          <p className="text-xs text-faint">
            Escribilo como te salga. Resalto lo que entiendo: el <span className="font-bold text-accent">monto</span>, el{" "}
            <span className="font-bold text-ok">medio</span> y la <span className="font-bold text-warn">categoría</span>.
          </p>
        </div>

        {!texto && (
          <div className="flex flex-col gap-2">
            <span className="text-[13px] font-bold">{frecuentes?.length ? "Lo que más cargás" : "Probá con"}</span>
            <div className="flex flex-wrap gap-1.5">
              {frecuentes?.length
                ? frecuentes.map((f) => (
                    <button
                      key={f.texto}
                      type="button"
                      onClick={() => setTexto(f.texto)}
                      className="press inline-flex min-h-11 items-center gap-2 rounded-2xl border border-line-strong bg-surface py-1 pr-3 pl-1.5 text-[13px] font-bold"
                    >
                      <IconoCat icono={f.categoria_icono} color={f.categoria_color} size={30} />
                      {f.descripcion}
                      <span className="num font-semibold text-muted">{monto(f.monto)}</span>
                    </button>
                  ))
                : EJEMPLOS.map((e) => (
                    <button key={e} type="button" onClick={() => setTexto(e)} className="press min-h-10 rounded-full border border-line-strong bg-surface px-3.5 text-[13px] font-bold">
                      {e}
                    </button>
                  ))}
            </div>
          </div>
        )}

        {vista && (
          <div key={vista.descripcion} className="anim-aparecer flex items-center gap-3 rounded-[22px] bg-surface p-4 shadow-soft">
            {vista.deuda_tipo ? (
              <IconoCat icono="persona" color={vista.deuda_tipo === "me_deben" ? "green" : "orange"} size={46} />
            ) : (
              <IconoCat icono={vista.categoria_icono} color={vista.categoria_color} size={46} />
            )}
            <div className="flex min-w-0 flex-1 flex-col">
              <span className="text-xs font-semibold text-muted">
                {vista.deuda_tipo === "me_deben" ? `Se suma a lo que te debe ${vista.deuda_nombre}` : vista.deuda_tipo === "debo" ? `Se anota en lo que le debés a ${vista.deuda_nombre}` : TIPO[vista.tipo]}
                {vista.cuotas ? ` en ${vista.cuotas} cuotas${vista.monto ? ` de ${monto(Math.round(Number(vista.monto) / vista.cuotas))}` : ""}` : ""}
                {vista.garantia_meses ? ` · garantía ${duracion(vista.garantia_meses)}` : ""}
                {vista.etiquetas?.length ? <span data-cat="pink" className="font-bold text-[var(--cat-fg)]"> · {vista.etiquetas.map((t) => `#${t}`).join(" ")}</span> : ""}
              </span>
              <span className="truncate text-lg font-extrabold">{vista.descripcion}</span>
              {!vista.deuda_tipo && <button
                type="button"
                onClick={() => setVerCategorias((v) => !v)}
                className="flex w-fit items-center gap-1 text-[13px] font-semibold text-muted underline-offset-2 hover:underline"
              >
                {vista.categoria ?? "Sin categoría"} <Pencil size={12} />
              </button>}
            </div>
            <span className={cx("display num shrink-0 text-[26px] font-bold", ingreso && "text-ok")}>
              {vista.monto ? monto(vista.monto, vista.moneda, ingreso ? "+" : "-") : "¿monto?"}
            </span>
          </div>
        )}

        {vista?.aviso && <Mensaje>{vista.aviso}</Mensaje>}

        {vista?.cuotas && vista.cuotas > 1 && !/cuotas?\s+(fijas\s+)?de\s/i.test(texto) && (
          <p className="-mt-2 text-xs text-faint">
            ¿Tiene interés? Escribí el valor de la cuota («{vista.cuotas} cuotas de 110k») y anoto lo que vas a pagar de verdad.
          </p>
        )}

        {vista && verCategorias && (
          <CategoriaPicker
            valor={categoriaFinal}
            tipo={ingreso ? "ingreso" : "gasto"}
            onCambio={(id) => {
              setCategoria(id);
              setVerCategorias(false);
            }}
          />
        )}

        {vista && (
          <div className="flex flex-col gap-2">
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-[13px] font-bold">{ingreso ? "Entró en" : "Pagaste con"}</span>
              <span className="text-xs text-faint">{medio ? "elegido por vos" : (vista.motivo_medio ?? "elegí uno")}</span>
            </div>
            <MedioChips valor={medioFinal} onCambio={setMedio} soloCredito={!!vista?.cuotas && vista.cuotas > 1 && !vista.deuda_tipo} />
          </div>
        )}

        {vista && (
          <div className="flex flex-col gap-2">
            <span className="text-[13px] font-bold">Cuándo</span>
            <FechaChips valor={fechaFinal} onCambio={setFecha} />
          </div>
        )}

        {vista && !vista.deuda_tipo && fechaFinal < hoyISO() && (
          <FueraDeSaldo activo={fueraFinal} onCambio={setFuera} cuenta={cuentaMov} ingreso={vista.tipo === "ingreso"} sugerido={sugerirFuera} />
        )}

        {error && <Mensaje>{error}</Mensaje>}

        <input
          ref={fotoRef}
          type="file"
          accept="image/*,application/pdf"
          capture="environment"
          className="hidden"
          onChange={(e) => {
            setArchivo(e.target.files?.[0] ?? null);
            e.target.value = "";
          }}
        />
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => fotoRef.current?.click()}
            aria-label={archivo ? `Comprobante: ${archivo.name}` : "Sacar foto del ticket"}
            title={archivo ? archivo.name : "Sacar foto del ticket"}
            className={cx(
              "press flex min-h-14 w-14 shrink-0 items-center justify-center rounded-2xl border",
              archivo ? "border-ok bg-ok-soft text-ok" : "border-line-strong bg-surface text-ink"
            )}
          >
            {archivo ? <FileCheck2 size={22} /> : <Camera size={22} />}
          </button>
          <Boton type="submit" variante="acento" disabled={!texto.trim() || guardando} className="min-h-14 flex-1 text-base font-extrabold">
            {guardando ? "Guardando…" : medioFinal || !vista ? "Guardar" : "Guardar en la bandeja"}
          </Boton>
        </div>
      </form>
    </Sheet>
  );
}
