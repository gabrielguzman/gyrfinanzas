"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { api, ApiError, type Cuenta, type Deuda, type DeudaDetalle, type TipoDeuda } from "@/lib/api";
import { hoyISO, monto } from "@/lib/format";
import { vibrar } from "@/lib/hooks";
import { FilaCuenta } from "./CuentaForms";
import { MovimientoFila } from "./MovimientoFila";
import { FechaChips, MedioChips, OpcionesLista } from "./Selectores";
import { Sheet } from "./Sheet";
import { useApp } from "./Shell";
import { Boton, Campo, Chip, IconoCat, Lista, Mensaje, cx, inputCls } from "./ui";

export function iconoDeuda(d: Pick<Deuda, "tipo">): [string, string] {
  if (d.tipo === "prestamo") return ["prestamo", "blue"];
  if (d.tipo === "debo") return ["persona", "orange"];
  return ["persona", "green"];
}

const num = (s: string) => s.replace(/\./g, "").replace(",", ".");

/** Detalle de una deuda: estado, registrar pago/cobro e historial. */
export function DeudaSheet({ id, onCerrar }: { id: string | null; onCerrar: () => void }) {
  const { aviso, refrescar } = useApp();
  const { data: d, mutate } = useSWR<DeudaDetalle>(id ? `/deudas/${id}` : null);
  const [modo, setModo] = useState<"pago" | "aumento" | null>(null);
  const [valor, setValor] = useState("");
  const [medio, setMedio] = useState<string | null>(null);
  const [fecha, setFecha] = useState(hoyISO());
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    setModo(null);
    setError(null);
  }, [id]);

  if (!id) return null;
  const cobra = d?.tipo === "me_deben";
  const etiquetaPago = cobra ? "Registrar cobro" : "Registrar pago";
  const etiquetaAumento = cobra ? "Le presté más" : d?.tipo === "debo" ? "Me prestó más" : null;

  function abrir(m: "pago" | "aumento") {
    setModo(m);
    setError(null);
    setFecha(hoyISO());
    setMedio(null);
    setValor(m === "pago" && d ? String(Number(d.cuota_sugerida ?? d.saldo)) : "");
  }

  async function registrar() {
    if (!d || !modo) return;
    setOcupado(true);
    setError(null);
    try {
      const r = await api.post<DeudaDetalle>(`/deudas/${d.id}/movimientos`, {
        accion: modo, monto: num(valor) || undefined, fecha, medio_pago_id: medio,
      });
      vibrar();
      await mutate(r, { revalidate: false });
      refrescar();
      aviso(r.cerrada ? `${d.nombre}: saldada` : modo === "pago" ? (cobra ? "Cobro registrado" : "Pago registrado") : "Registrado");
      setModo(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No pude conectar con el servidor");
    } finally {
      setOcupado(false);
    }
  }

  return (
    <Sheet abierto={!!id} onCerrar={onCerrar}>
      {!d ? (
        <div className="esqueleto h-48" />
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex items-center gap-3">
            <IconoCat icono={iconoDeuda(d)[0]} color={iconoDeuda(d)[1]} size={48} />
            <div className="flex min-w-0 flex-1 flex-col">
              <span className="text-xs font-semibold text-muted">
                {d.tipo === "prestamo" ? "Préstamo" : d.tipo === "debo" ? "Le debés" : "Te debe"}
                {d.cerrada && " · saldada"}
              </span>
              <h2 className="line-clamp-2 text-xl leading-tight font-extrabold">{d.nombre}</h2>
            </div>
            <span className={cx("display num text-[28px] font-bold", cobra && "text-ok")}>{monto(d.saldo, d.moneda)}</span>
          </div>

          <dl className="grid grid-cols-2 gap-2.5 text-sm">
            {d.tipo === "prestamo" && d.cuotas_total != null && (
              <div className="rounded-2xl bg-surface p-3">
                <dt className="text-muted">Cuotas</dt>
                <dd className="font-bold">{d.cuotas_pagadas} de {d.cuotas_total} pagadas</dd>
              </div>
            )}
            {d.cuota && (
              <div className="rounded-2xl bg-surface p-3">
                <dt className="text-muted">Cuota</dt>
                <dd className="num font-bold">{monto(d.cuota)}{d.dia_vencimiento ? `, el ${d.dia_vencimiento}` : ""}</dd>
              </div>
            )}
            {d.tna && (
              <div className="rounded-2xl bg-surface p-3">
                <dt className="text-muted">Tasa</dt>
                <dd className="font-bold">{d.indexacion === "uva" ? `UVA + ${Number(d.tna)}%` : `TNA ${Number(d.tna)}%`}</dd>
              </div>
            )}
            <div className="rounded-2xl bg-surface p-3">
              <dt className="text-muted">{cobra ? "Te devolvió" : "Pagaste"}</dt>
              <dd className="num font-bold">{monto(d.pagado)}{Number(d.intereses_pagados) > 0 && <span className="font-semibold text-muted">, {monto(d.intereses_pagados)} de interés</span>}</dd>
            </div>
          </dl>

          {modo ? (
            <div className="flex flex-col gap-4 rounded-[22px] border border-line-strong p-4">
              <Campo label="Monto">
                <input className={inputCls + " num"} inputMode="decimal" value={valor} onChange={(e) => setValor(e.target.value)} autoFocus />
              </Campo>
              <div className="flex flex-col gap-2">
                <span className="text-[13px] font-bold">{(modo === "pago") !== cobra ? "Con qué pagaste" : "Dónde entró"}</span>
                <MedioChips valor={medio} onCambio={setMedio} />
                {d.cuenta_id && !medio && <span className="text-xs text-faint">Si no elegís, uso la cuenta de débito de este préstamo.</span>}
              </div>
              <div className="flex flex-col gap-2">
                <span className="text-[13px] font-bold">Cuándo</span>
                <FechaChips valor={fecha} onCambio={setFecha} />
              </div>
              {error && <Mensaje>{error}</Mensaje>}
              <div className="flex gap-2">
                <Boton variante="linea" onClick={() => setModo(null)}>Cancelar</Boton>
                <Boton variante="acento" className="flex-1" disabled={ocupado || !Number(num(valor))} onClick={registrar}>Guardar</Boton>
              </div>
            </div>
          ) : (
            !d.cerrada && (
              <div className="flex gap-2">
                <Boton variante="acento" className="flex-1" onClick={() => abrir("pago")}>{etiquetaPago}</Boton>
                {etiquetaAumento && <Boton variante="linea" onClick={() => abrir("aumento")}>{etiquetaAumento}</Boton>}
              </div>
            )
          )}

          {d.movimientos.length > 0 && (
            <div className="flex flex-col gap-2">
              <span className="text-[13px] font-bold">Historial</span>
              <Lista>{d.movimientos.map((m) => <MovimientoFila key={m.id} mov={m} />)}</Lista>
            </div>
          )}

          <div className="flex flex-wrap gap-2 text-sm">
            {d.pagos === 0 && d.movimientos.length === 0 ? (
              <button
                className="font-bold text-danger"
                onClick={async () => {
                  await api.del(`/deudas/${d.id}`);
                  refrescar();
                  aviso(`Borrada: ${d.nombre}`);
                  onCerrar();
                }}
              >
                Borrar esta deuda
              </button>
            ) : (
              <button
                className="font-bold text-muted"
                onClick={async () => {
                  await api.patch(`/deudas/${d.id}`, { cerrada: !d.cerrada });
                  await mutate();
                  refrescar();
                }}
              >
                {d.cerrada ? "Reabrir" : "Marcar como saldada"}
              </button>
            )}
          </div>
        </div>
      )}
    </Sheet>
  );
}

const TIPOS: { id: TipoDeuda; titulo: string; texto: string }[] = [
  { id: "prestamo", titulo: "Préstamo con cuotas", texto: "Banco, financiera, Mercado Pago" },
  { id: "debo", titulo: "Le debo a alguien", texto: "Un familiar, un amigo" },
  { id: "me_deben", titulo: "Me deben", texto: "Le prestaste a alguien" },
];

export function NuevaDeudaSheet({ abierto, onCerrar }: { abierto: boolean; onCerrar: () => void }) {
  const { aviso, refrescar } = useApp();
  const { data: cuentas } = useSWR<Cuenta[]>(abierto ? "/cuentas" : null);
  const [tipo, setTipo] = useState<TipoDeuda>("prestamo");
  const [nombre, setNombre] = useState("");
  const [saldo, setSaldo] = useState("");
  const [cuota, setCuota] = useState("");
  const [total, setTotal] = useState("");
  const [pagadas, setPagadas] = useState("0");
  const [tna, setTna] = useState("");
  const [uva, setUva] = useState(false);
  const [dia, setDia] = useState("");
  const [cuenta, setCuenta] = useState("");
  const [error, setError] = useState<string | null>(null);
  const prestamo = tipo === "prestamo";

  async function crear() {
    setError(null);
    try {
      await api.post("/deudas", {
        tipo, nombre: nombre.trim(), monto_inicial: num(saldo) || "0",
        tna: tna ? num(tna) : null,
        indexacion: uva ? "uva" : "fija",
        cuota: prestamo && cuota ? num(cuota) : null,
        cuotas_total: prestamo && total ? Number(total) : null,
        cuotas_pagadas: prestamo ? Number(pagadas || 0) : 0,
        dia_vencimiento: prestamo && dia ? Number(dia) : null,
        cuenta_id: prestamo && cuenta ? cuenta : null,
      });
      refrescar();
      aviso("Deuda cargada");
      setNombre(""); setSaldo(""); setCuota(""); setTotal(""); setPagadas("0"); setTna(""); setDia(""); setCuenta("");
      onCerrar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No pude conectar con el servidor");
    }
  }

  return (
    <Sheet abierto={abierto} onCerrar={onCerrar} titulo="Nueva deuda">
      <div className="grid gap-2" role="radiogroup" aria-label="Tipo de deuda">
        {TIPOS.map((t) => (
          <button
            key={t.id}
            role="radio"
            aria-checked={tipo === t.id}
            onClick={() => setTipo(t.id)}
            className={cx("press flex min-h-14 items-center gap-3 rounded-2xl border bg-surface px-3 text-left", tipo === t.id ? "border-ink" : "border-transparent")}
          >
            <IconoCat icono={iconoDeuda({ tipo: t.id })[0]} color={iconoDeuda({ tipo: t.id })[1]} size={34} />
            <span className="flex flex-col">
              <span className="text-sm font-bold">{t.titulo}</span>
              <span className="text-xs text-muted">{t.texto}</span>
            </span>
          </button>
        ))}
      </div>
      <Campo label={prestamo ? "Nombre del préstamo" : tipo === "debo" ? "¿A quién?" : "¿Quién?"}>
        <input className={inputCls} value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder={prestamo ? "Préstamo personal Galicia" : "Juan"} />
      </Campo>
      <Campo label={prestamo ? "Lo que te falta pagar de capital" : tipo === "debo" ? "Cuánto le debés hoy" : "Cuánto te debe hoy"} ayuda={prestamo ? "Está en el home banking como «saldo» o «capital adeudado»." : undefined}>
        <input className={inputCls + " num"} inputMode="decimal" value={saldo} onChange={(e) => setSaldo(e.target.value)} placeholder="0" />
      </Campo>
      {prestamo && (
        <>
          <div className="grid grid-cols-2 gap-3">
            <Campo label="Cuota por mes"><input className={inputCls + " num"} inputMode="decimal" value={cuota} onChange={(e) => setCuota(e.target.value)} /></Campo>
            <Campo label="Día de vencimiento"><input className={inputCls} inputMode="numeric" value={dia} onChange={(e) => setDia(e.target.value)} placeholder="10" /></Campo>
            <Campo label="Cuotas en total"><input className={inputCls} inputMode="numeric" value={total} onChange={(e) => setTotal(e.target.value)} placeholder="24" /></Campo>
            <Campo label="Ya pagadas"><input className={inputCls} inputMode="numeric" value={pagadas} onChange={(e) => setPagadas(e.target.value)} /></Campo>
          </div>
          <div className="flex flex-col gap-2">
            <span className="text-[13px] font-semibold text-muted">Tasa</span>
            <div className="flex flex-wrap items-center gap-2">
              <Chip activo={!uva} onClick={() => setUva(false)}>Tasa fija</Chip>
              <Chip activo={uva} onClick={() => setUva(true)}>UVA</Chip>
              <span className="flex items-center gap-1.5 text-sm font-bold text-muted">
                {uva ? "UVA +" : "TNA"}
                <input className={inputCls + " num w-24"} inputMode="decimal" value={tna} onChange={(e) => setTna(e.target.value)} placeholder={uva ? "9" : "45"} aria-label="Tasa nominal anual" />
                %
              </span>
            </div>
          </div>
          {cuentas && cuentas.filter((c) => c.tipo !== "tarjeta_credito").length > 0 && (
            <div className="flex flex-col gap-2">
              <span className="text-[13px] font-semibold text-muted">¿De qué cuenta se debita? (opcional)</span>
              <OpcionesLista
                opciones={cuentas.filter((c) => c.tipo !== "tarjeta_credito")}
                valor={cuenta}
                onCambio={(v) => setCuenta(v === cuenta ? "" : v)}
                render={(c) => <FilaCuenta c={c} />}
              />
            </div>
          )}
        </>
      )}
      {tipo === "debo" && (
        <Campo label="¿Te cobra interés? TNA % (opcional)">
          <input className={inputCls + " num w-32"} inputMode="decimal" value={tna} onChange={(e) => setTna(e.target.value)} placeholder="0" />
        </Campo>
      )}
      {error && <Mensaje>{error}</Mensaje>}
      <Boton variante="acento" disabled={!nombre.trim() || !Number(num(saldo))} onClick={crear}>Guardar</Boton>
    </Sheet>
  );
}
