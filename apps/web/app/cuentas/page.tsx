"use client";

import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { ArrowLeftRight, Plus, Goal, Landmark, Repeat, Settings } from "lucide-react";
import { COLOR_CUENTA, NuevaCuentaSheet, NuevoMedioSheet, TransferenciaSheet } from "@/components/CuentaForms";
import { useContador } from "@/lib/hooks";
import { Salir } from "@/components/Shell";
import { Boton, Esqueleto, IconoCat, Lista, Seccion, Titulo, Vacio } from "@/components/ui";
import type { Cuenta, Inicio, MedioPago } from "@/lib/api";
import { monto, TIPO_CUENTA, TIPO_MEDIO } from "@/lib/format";

function Total({ t }: { t: Inicio["totales"][number] }) {
  const v = useContador(Number(t.disponible));
  return (
    <div className="flex flex-col gap-1">
      <span className="text-sm font-semibold text-muted">Disponible en {t.moneda === "ARS" ? "pesos" : "dólares"}</span>
      <span className="display num text-[44px] leading-none font-bold">{monto(Math.round(v), t.moneda)}</span>
      <span className="text-[13px] text-muted">
        {monto(t.en_cuentas, t.moneda)} en cuentas menos {monto(t.deuda_tarjetas, t.moneda)} de tarjetas
      </span>
    </div>
  );
}

export default function CuentasPage() {
  const { data: cuentas } = useSWR<Cuenta[]>("/cuentas");
  const { data: medios } = useSWR<MedioPago[]>("/medios-pago");
  const { data: inicio } = useSWR<Inicio>("/inicio");
  const [nuevaCuenta, setNuevaCuenta] = useState(false);
  const [nuevoMedio, setNuevoMedio] = useState(false);
  const [transfer, setTransfer] = useState<{ abierto: boolean; destino?: string }>({ abierto: false });

  const plata = cuentas?.filter((c) => c.tipo !== "tarjeta_credito") ?? [];
  const tarjetas = cuentas?.filter((c) => c.tipo === "tarjeta_credito") ?? [];
  const nombreCuenta = (id: string) => cuentas?.find((c) => c.id === id)?.nombre ?? "";

  return (
    <div className="flex flex-col gap-7">
      <Titulo extra={<Boton variante="linea" onClick={() => setNuevaCuenta(true)}><Plus size={18} /> Nueva cuenta</Boton>}>Cuentas</Titulo>
      <div className="grid grid-cols-2 gap-3 lg:hidden">
        <Link href="/patrimonio" className="press flex items-center gap-3 rounded-[20px] bg-surface p-3.5 shadow-soft">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[14px] bg-accent-soft text-accent"><Landmark size={19} /></span>
          <span className="flex min-w-0 flex-col"><span className="text-sm font-bold">Patrimonio</span><span className="truncate text-xs text-muted">Todo lo que tenés</span></span>
        </Link>
        <Link href="/metas" className="press flex items-center gap-3 rounded-[20px] bg-surface p-3.5 shadow-soft">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[14px] bg-ok-soft text-ok"><Goal size={19} /></span>
          <span className="flex min-w-0 flex-col"><span className="text-sm font-bold">Metas</span><span className="truncate text-xs text-muted">Lo que estás juntando</span></span>
        </Link>
        <Link href="/fijos" className="press flex items-center gap-3 rounded-[20px] bg-surface p-3.5 shadow-soft">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[14px] bg-warn-soft text-warn-ink"><Repeat size={19} /></span>
          <span className="flex min-w-0 flex-col"><span className="text-sm font-bold">Gastos fijos</span><span className="truncate text-xs text-muted">Alquiler, servicios</span></span>
        </Link>
        <Link href="/ajustes" className="press flex items-center gap-3 rounded-[20px] bg-surface p-3.5 shadow-soft">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[14px] bg-surface-2 text-muted"><Settings size={19} /></span>
          <span className="flex min-w-0 flex-col"><span className="text-sm font-bold">Ajustes</span><span className="truncate text-xs text-muted">Avisos, reglas, exportar</span></span>
        </Link>
      </div>

      {inicio ? (
        <div className="flex flex-col gap-6 sm:flex-row sm:gap-12">{inicio.totales.map((t) => <Total key={t.moneda} t={t} />)}</div>
      ) : (
        <Esqueleto className="h-24" />
      )}

      {cuentas?.length === 0 && (
        <Vacio titulo="Todavía no hay cuentas" accion={<Boton variante="acento" onClick={() => setNuevaCuenta(true)}><Plus size={18} /> Crear la primera</Boton>}>
          Creá el banco donde cobrás, Mercado Pago, el efectivo y cada tarjeta de crédito.
        </Vacio>
      )}

      <div className="grid gap-7 lg:grid-cols-2 lg:items-start">
        <div className="flex flex-col gap-7">
          {plata.length > 0 && (
            <Seccion titulo="Dónde está tu plata">
              <Lista>
                {plata.map((c) => (
                  <div key={c.id} className="flex min-h-16 items-center gap-3 px-4 py-3">
                    <IconoCat icono={c.tipo} color={COLOR_CUENTA[c.tipo]} />
                    <div className="flex flex-1 flex-col">
                      <span className="text-[15px] font-bold">{c.nombre}</span>
                      <span className="text-xs text-muted">{TIPO_CUENTA[c.tipo]}{c.moneda === "USD" ? " en dólares" : ""}</span>
                    </div>
                    <span className="num font-extrabold">{monto(c.saldo, c.moneda)}</span>
                  </div>
                ))}
              </Lista>
            </Seccion>
          )}

          {tarjetas.length > 0 && (
            <Seccion titulo="Tarjetas">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
                {tarjetas.map((c) => {
                  const deuda = Math.max(0, -Number(c.saldo));
                  return (
                    <div key={c.id} className="relative flex flex-col gap-4 rounded-[22px] bg-slab p-5 text-slab-ink shadow-soft">
                      <div className="flex flex-col gap-0.5">
                        <Link href={`/tarjetas/${c.id}`} className="font-bold after:absolute after:inset-0 after:rounded-[22px] after:content-['']">
                          {c.nombre}
                        </Link>
                        <span className="text-xs text-slab-muted">
                          {c.dia_cierre ? `Cierra el ${c.dia_cierre}` : "Sin día de cierre"}
                          {c.dia_vencimiento ? ` y vence el ${c.dia_vencimiento}` : ""}
                        </span>
                      </div>
                      <div>
                        <span className="text-xs text-slab-muted">Debés · tocá para ver cuotas y resúmenes</span>
                        <p className="display num text-[32px] leading-none font-bold">{monto(deuda, c.moneda)}</p>
                      </div>
                      {deuda > 0 && (
                        <button
                          onClick={() => setTransfer({ abierto: true, destino: c.id })}
                          className="press relative z-10 min-h-11 rounded-2xl bg-white/12 text-sm font-bold"
                        >
                          Pagar el resumen
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            </Seccion>
          )}

          {cuentas && cuentas.length > 0 && (
            <Boton variante="linea" onClick={() => setTransfer({ abierto: true })} className="w-fit">
              <ArrowLeftRight size={18} /> Mover plata entre cuentas
            </Boton>
          )}
        </div>

        {cuentas && cuentas.length > 0 && (
          <Seccion
            titulo="Medios de pago"
            extra={<button onClick={() => setNuevoMedio(true)} className="press text-sm font-bold text-accent">Agregar</button>}
          >
            <p className="-mt-1 text-sm text-muted">Son las formas de pagar que reconozco cuando escribís. Cada una descuenta de una cuenta.</p>
            <Lista>
              {medios?.map((m) => (
                <div key={m.id} className="flex flex-col gap-1 px-4 py-3">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-[15px] font-bold">{m.nombre}</span>
                    <span className="text-xs font-semibold text-faint">{TIPO_MEDIO[m.tipo]}</span>
                  </div>
                  <span className="text-[13px] text-muted">
                    Descuenta de {nombreCuenta(m.cuenta_id)}
                    {m.alias && <>. Lo reconozco por {m.alias.split(",").filter(Boolean).map((a) => `«${a.trim()}»`).join(", ")}</>}
                  </span>
                </div>
              ))}
              {medios?.length === 0 && <p className="p-4 text-sm text-muted">Todavía no hay medios de pago.</p>}
            </Lista>
          </Seccion>
        )}
      </div>

      <NuevaCuentaSheet abierto={nuevaCuenta} onCerrar={() => setNuevaCuenta(false)} />
      <NuevoMedioSheet abierto={nuevoMedio} onCerrar={() => setNuevoMedio(false)} />
      <TransferenciaSheet key={transfer.destino ?? "libre"} abierto={transfer.abierto} destinoInicial={transfer.destino} onCerrar={() => setTransfer({ abierto: false })} />
      <div className="lg:hidden"><Salir /></div>
    </div>
  );
}
