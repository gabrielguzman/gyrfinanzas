"use client";

import { useRef, useState } from "react";
import { Check, Paperclip, Trash2 } from "lucide-react";
import { api, ApiError, type Movimiento } from "@/lib/api";
import { monto } from "@/lib/format";
import { vibrar } from "@/lib/hooks";
import { AdjuntarBoton } from "./AdjuntarBoton";
import { MedioChips } from "./Selectores";
import { useApp } from "./Shell";
import { Boton, IconoCat, cx } from "./ui";

const UMBRAL = 96;
const ORIGEN: Record<string, string> = { texto: "Escrito", telegram: "Telegram", foto: "Foto", pdf: "PDF", voz: "Voz", manual: "A mano" };

/** Fila de la bandeja: deslizá a la derecha para confirmar, a la izquierda para borrar. */
export function BandejaItem({ mov }: { mov: Movimiento }) {
  const { aviso, refrescar, abrirMovimiento } = useApp();
  const [dx, setDx] = useState(0);
  const [arrastrando, setArrastrando] = useState(false);
  const [saliendo, setSaliendo] = useState<"der" | "izq" | null>(null);
  const [oculto, setOculto] = useState(false);
  const inicio = useRef<{ x: number; y: number; eje: "x" | "y" | null } | null>(null);
  const puedeConfirmar = !!mov.medio_pago_id;

  async function confirmar() {
    if (!puedeConfirmar) {
      aviso("Elegí con qué pagaste y después confirmalo");
      return;
    }
    vibrar();
    setSaliendo("der");
    try {
      await api.post(`/movimientos/${mov.id}/confirmar`);
      window.setTimeout(refrescar, 260);
      aviso(`Confirmado: ${mov.descripcion}`, {
        deshacer: () => {
          setSaliendo(null);
          setDx(0);
          return api.post(`/movimientos/${mov.id}/desconfirmar`);
        },
      });
    } catch (e) {
      setSaliendo(null);
      aviso(e instanceof ApiError ? e.message : "No pude conectar con el servidor");
    }
  }

  function borrar() {
    vibrar(20);
    setSaliendo("izq");
    window.setTimeout(() => setOculto(true), 260);
    // Se borra de verdad a los 5 s, salvo que toques «Deshacer».
    const t = window.setTimeout(async () => {
      try {
        await api.del(`/movimientos/${mov.id}`);
      } finally {
        refrescar();
      }
    }, 5000);
    aviso(`Borrado: ${mov.descripcion}`, {
      deshacer: () => {
        window.clearTimeout(t);
        setOculto(false);
        setSaliendo(null);
        setDx(0);
      },
    });
  }

  async function correr(fn: () => Promise<unknown>, ok?: string) {
    try {
      await fn();
      refrescar();
      if (ok) aviso(ok);
    } catch (e) {
      aviso(e instanceof ApiError ? e.message : "No pude conectar con el servidor");
    }
  }

  // ---- gesto ----
  function down(e: React.PointerEvent) {
    if ((e.target as HTMLElement).closest("button, a, input, label")) return;
    inicio.current = { x: e.clientX, y: e.clientY, eje: null };
  }
  function move(e: React.PointerEvent) {
    const i = inicio.current;
    if (!i) return;
    const mx = e.clientX - i.x, my = e.clientY - i.y;
    if (!i.eje && Math.hypot(mx, my) > 8) i.eje = Math.abs(mx) > Math.abs(my) ? "x" : "y";
    if (i.eje !== "x") return;
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
    setArrastrando(true);
    const limitado = mx > 0 && !puedeConfirmar ? Math.min(mx, 40) : mx;
    setDx(limitado);
  }
  function up() {
    const fue = dx;
    inicio.current = null;
    setArrastrando(false);
    if (fue > UMBRAL && puedeConfirmar) confirmar();
    else if (fue < -UMBRAL) borrar();
    else setDx(0);
  }

  if (oculto) return null;
  const transform = saliendo === "der" ? "translateX(110%)" : saliendo === "izq" ? "translateX(-110%)" : `translateX(${dx}px)`;
  const listo = Math.abs(dx) > UMBRAL;

  return (
    <div className={cx("relative overflow-hidden rounded-[22px] transition-[max-height,opacity] duration-300", saliendo ? "max-h-0 opacity-0" : "max-h-[600px]")}>
      {/* Fondo que se revela al deslizar */}
      <div className="absolute inset-0 flex items-center justify-between px-6 text-sm font-bold" aria-hidden>
        <span className={cx("flex items-center gap-2 transition-opacity", dx > 0 ? "opacity-100" : "opacity-0", "text-ok")}>
          <Check size={22} className={listo ? "anim-pop" : ""} /> Confirmar
        </span>
        <span className={cx("flex items-center gap-2 transition-opacity", dx < 0 ? "opacity-100" : "opacity-0", "text-danger")}>
          Borrar <Trash2 size={20} className={listo ? "anim-pop" : ""} />
        </span>
      </div>
      <div
        className={cx("absolute inset-0 transition-colors", dx > 0 ? "bg-ok-soft" : dx < 0 ? "bg-danger-soft" : "bg-transparent")}
        aria-hidden
      />

      <div
        onPointerDown={down}
        onPointerMove={move}
        onPointerUp={up}
        onPointerCancel={up}
        className="relative flex touch-pan-y flex-col gap-3 rounded-[22px] bg-surface p-4 shadow-soft"
        style={{ transform, transition: arrastrando ? "none" : "transform 0.28s cubic-bezier(0.2,0.8,0.2,1)" }}
      >
        <div className="flex items-center gap-3">
          <IconoCat icono={mov.categoria_icono} color={mov.categoria_color} />
          <div className="flex min-w-0 flex-1 flex-col">
            <div className="flex items-baseline justify-between gap-3">
              <span className="truncate text-base font-bold">{mov.descripcion}</span>
              <span className={cx("num shrink-0 text-base font-extrabold", mov.tipo === "ingreso" && "text-ok")}>
                {monto(mov.monto, mov.moneda, mov.tipo === "ingreso" ? "+" : "-")}
              </span>
            </div>
            <span className="truncate text-[13px] text-muted">
              {mov.texto_original ? `${ORIGEN[mov.origen] ?? "Cargado"}: «${mov.texto_original}»` : mov.categoria ?? "Sin categoría"}
            </span>
          </div>
        </div>

        {!mov.medio_pago_id ? (
          <div className="flex flex-col gap-2">
            <span className="text-[13px] font-bold">¿Con qué pagaste?</span>
            <MedioChips valor={null} onCambio={(id) => correr(() => api.patch(`/movimientos/${mov.id}`, { medio_pago_id: id }))} />
          </div>
        ) : (
          <span className="text-[13px] text-muted">
            Con <b className="text-ink">{mov.medio_pago}</b>
            {mov.categoria && <> en <b className="text-ink">{mov.categoria}</b></>}
          </span>
        )}

        <div className="flex items-center gap-2">
          {mov.adjuntos.length > 0 ? (
            <span
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-ok-soft text-ok"
              title={mov.adjuntos.map((a) => a.nombre).join(", ")}
              aria-label="Tiene comprobante"
            >
              <Paperclip size={17} />
            </span>
          ) : (
            <AdjuntarBoton
              soloIcono
              texto="Adjuntar comprobante"
              className="w-11 shrink-0 px-0"
              onArchivo={(f) => correr(() => api.subir(`/movimientos/${mov.id}/adjuntos/subir`, f), "Comprobante adjuntado")}
            />
          )}
          <Boton variante="linea" onClick={() => abrirMovimiento(mov.id)}>Editar</Boton>
          <Boton onClick={confirmar} disabled={!puedeConfirmar} className="flex-1">
            Confirmar
          </Boton>
        </div>
      </div>
    </div>
  );
}
