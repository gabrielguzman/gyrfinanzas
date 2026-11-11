"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, ApiError, type Cuenta, type Moneda, type TipoCuenta, type TipoMedio } from "@/lib/api";
import { hoyISO, monto, TIPO_CUENTA, TIPO_MEDIO } from "@/lib/format";
import { FechaChips, OpcionesLista } from "./Selectores";
import { Sheet } from "./Sheet";
import { useApp } from "./Shell";
import { Boton, Campo, Chip, IconoCat, Mensaje, inputCls } from "./ui";

function useEnvio() {
  const { aviso, refrescar } = useApp();
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function enviar(fn: () => Promise<unknown>, ok: string) {
    setOcupado(true);
    setError(null);
    try {
      await fn();
      refrescar();
      aviso(ok);
      return true;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No pude conectar con el servidor");
      return false;
    } finally {
      setOcupado(false);
    }
  }
  return { ocupado, error, enviar };
}

export const COLOR_CUENTA: Record<TipoCuenta, string> = { banco: "blue", billetera: "teal", efectivo: "green", tarjeta_credito: "orange" };

export function FilaCuenta({ c }: { c: Cuenta }) {
  return (
    <>
      <IconoCat icono={c.tipo} color={COLOR_CUENTA[c.tipo]} size={38} />
      <span className="flex flex-1 flex-col">
        <span className="text-[15px] font-bold">{c.nombre}</span>
        <span className="text-xs text-muted">{TIPO_CUENTA[c.tipo]}</span>
      </span>
      <span className="num text-sm font-bold text-muted">{monto(c.saldo, c.moneda)}</span>
    </>
  );
}

function medioSugerido(nombre: string, tipo: TipoCuenta): { nombre: string; tipo: TipoMedio; alias: string } {
  const primera = nombre.trim().split(/\s+/)[0]?.toLowerCase() ?? "";
  switch (tipo) {
    case "banco":
      return { nombre: `Débito ${nombre}`, tipo: "debito", alias: `debito,${primera}` };
    case "billetera":
      return { nombre, tipo: "qr", alias: primera === "mercado" ? "mp,mercadopago,mercado pago" : primera };
    case "efectivo":
      return { nombre: "Efectivo", tipo: "efectivo", alias: "efectivo,cash" };
    case "tarjeta_credito":
      return { nombre, tipo: "credito", alias: primera };
  }
}

const PLACEHOLDER: Record<TipoCuenta, string> = { banco: "Galicia", billetera: "Mercado Pago", efectivo: "Efectivo", tarjeta_credito: "Visa Galicia" };

export function NuevaCuentaSheet({ abierto, onCerrar }: { abierto: boolean; onCerrar: () => void }) {
  const { ocupado, error, enviar } = useEnvio();
  const [nombre, setNombre] = useState("");
  const [tipo, setTipo] = useState<TipoCuenta>("banco");
  const [moneda, setMoneda] = useState<Moneda>("ARS");
  const [saldo, setSaldo] = useState("");
  const [cierre, setCierre] = useState("");
  const [venc, setVenc] = useState("");
  const [conMedio, setConMedio] = useState(true);
  const esTarjeta = tipo === "tarjeta_credito";
  const sugerido = medioSugerido(nombre || PLACEHOLDER[tipo], tipo);

  async function guardar() {
    const valor = Number(saldo.replace(/\./g, "").replace(",", ".") || 0);
    const ok = await enviar(async () => {
      const cuenta = await api.post<Cuenta>("/cuentas", {
        nombre: nombre.trim(), tipo, moneda,
        saldo_inicial: String(esTarjeta ? -Math.abs(valor) : valor),
        dia_cierre: esTarjeta && cierre ? Number(cierre) : null,
        dia_vencimiento: esTarjeta && venc ? Number(venc) : null,
      });
      if (conMedio) await api.post("/medios-pago", { ...medioSugerido(nombre, tipo), cuenta_id: cuenta.id });
    }, "Cuenta creada");
    if (ok) {
      setNombre(""); setSaldo(""); setCierre(""); setVenc("");
      onCerrar();
    }
  }

  return (
    <Sheet abierto={abierto} onCerrar={onCerrar} titulo="Nueva cuenta">
      <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Tipo de cuenta">
        {(Object.keys(TIPO_CUENTA) as TipoCuenta[]).map((t) => (
          <button
            key={t}
            role="radio"
            aria-checked={tipo === t}
            onClick={() => setTipo(t)}
            className={`press flex min-h-14 items-center gap-2.5 rounded-2xl border bg-surface px-3 text-left text-sm font-bold ${tipo === t ? "border-ink" : "border-transparent"}`}
          >
            <IconoCat icono={t} color={COLOR_CUENTA[t]} size={32} />
            {TIPO_CUENTA[t]}
          </button>
        ))}
      </div>
      <Campo label="Nombre">
        <input className={inputCls} value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder={PLACEHOLDER[tipo]} />
      </Campo>
      <div className="flex gap-1.5">
        {(["ARS", "USD"] as Moneda[]).map((m) => (
          <Chip key={m} activo={moneda === m} onClick={() => setMoneda(m)}>{m === "ARS" ? "Pesos" : "Dólares"}</Chip>
        ))}
      </div>
      <Campo label={esTarjeta ? "Lo que ya debés en esta tarjeta" : "Cuánto tenés hoy"}>
        <input className={inputCls + " num"} inputMode="decimal" value={saldo} onChange={(e) => setSaldo(e.target.value)} placeholder="0" />
      </Campo>
      {esTarjeta && (
        <div className="grid grid-cols-2 gap-3">
          <Campo label="Día de cierre"><input className={inputCls} inputMode="numeric" value={cierre} onChange={(e) => setCierre(e.target.value)} placeholder="26" /></Campo>
          <Campo label="Día de vencimiento"><input className={inputCls} inputMode="numeric" value={venc} onChange={(e) => setVenc(e.target.value)} placeholder="5" /></Campo>
        </div>
      )}
      <label className="flex items-start gap-3 rounded-2xl bg-surface p-4 text-sm">
        <input type="checkbox" className="mt-0.5 h-5 w-5 accent-[var(--accent)]" checked={conMedio} onChange={(e) => setConMedio(e.target.checked)} />
        <span>
          Crear también el medio de pago <b>{sugerido.nombre}</b>
          <span className="mt-0.5 block text-xs text-muted">
            Lo voy a reconocer cuando escribas {sugerido.alias.split(",").filter(Boolean).map((a) => `«${a}»`).join(" o ")}.
          </span>
        </span>
      </label>
      {error && <Mensaje>{error}</Mensaje>}
      <Boton variante="acento" disabled={!nombre.trim() || ocupado} onClick={guardar} className="min-h-13">Crear cuenta</Boton>
    </Sheet>
  );
}

export function NuevoMedioSheet({ abierto, onCerrar }: { abierto: boolean; onCerrar: () => void }) {
  const { ocupado, error, enviar } = useEnvio();
  const { data: cuentas } = useSWR<Cuenta[]>(abierto ? "/cuentas" : null);
  const [nombre, setNombre] = useState("");
  const [tipo, setTipo] = useState<TipoMedio>("debito");
  const [cuenta, setCuenta] = useState("");
  const [alias, setAlias] = useState("");

  return (
    <Sheet abierto={abierto} onCerrar={onCerrar} titulo="Nuevo medio de pago">
      <div className="flex flex-wrap gap-1.5">
        {(Object.keys(TIPO_MEDIO) as TipoMedio[]).map((t) => (
          <Chip key={t} activo={tipo === t} onClick={() => setTipo(t)}>{TIPO_MEDIO[t]}</Chip>
        ))}
      </div>
      <Campo label="Nombre"><input className={inputCls} value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Débito Galicia" /></Campo>
      <div className="flex flex-col gap-2">
        <span className="text-[13px] font-semibold text-muted">¿De qué cuenta sale la plata?</span>
        <OpcionesLista opciones={cuentas ?? []} valor={cuenta} onCambio={setCuenta} render={(c) => <FilaCuenta c={c} />} />
      </div>
      <Campo label="Cómo lo escribís" ayuda="Palabras separadas por comas, por ejemplo: debito, galicia">
        <input className={inputCls} value={alias} onChange={(e) => setAlias(e.target.value)} placeholder="debito, galicia" />
      </Campo>
      {error && <Mensaje>{error}</Mensaje>}
      <Boton
        variante="acento"
        disabled={!nombre.trim() || !cuenta || ocupado}
        onClick={async () => {
          const ok = await enviar(() => api.post("/medios-pago", { nombre: nombre.trim(), tipo, cuenta_id: cuenta, alias }), "Medio de pago creado");
          if (ok) { setNombre(""); setAlias(""); onCerrar(); }
        }}
      >
        Crear medio de pago
      </Boton>
    </Sheet>
  );
}

export function TransferenciaSheet({ abierto, onCerrar, destinoInicial }: { abierto: boolean; onCerrar: () => void; destinoInicial?: string }) {
  const { ocupado, error, enviar } = useEnvio();
  const { data: cuentas } = useSWR<Cuenta[]>(abierto ? "/cuentas" : null);
  const [origen, setOrigen] = useState("");
  const [destino, setDestino] = useState(destinoInicial ?? "");
  const [valor, setValor] = useState("");
  const [fecha, setFecha] = useState(hoyISO());

  const dest = cuentas?.find((c) => c.id === destino);
  const esPago = dest?.tipo === "tarjeta_credito";
  const descripcion = esPago ? `Pago resumen ${dest!.nombre}` : "Transferencia";
  const deudaDestino = esPago ? Math.max(0, -Number(dest!.saldo)) : 0;

  return (
    <Sheet abierto={abierto} onCerrar={onCerrar} titulo={esPago ? "Pagar resumen" : "Mover plata"}>
      <div className="flex flex-col gap-2">
        <span className="text-[13px] font-semibold text-muted">Desde</span>
        <OpcionesLista
          opciones={cuentas?.filter((c) => c.tipo !== "tarjeta_credito" && c.id !== destino) ?? []}
          valor={origen}
          onCambio={setOrigen}
          render={(c) => <FilaCuenta c={c} />}
        />
      </div>
      <div className="flex flex-col gap-2">
        <span className="text-[13px] font-semibold text-muted">Hacia (elegí la tarjeta para pagar su resumen)</span>
        <OpcionesLista opciones={cuentas?.filter((c) => c.id !== origen) ?? []} valor={destino} onCambio={setDestino} render={(c) => <FilaCuenta c={c} />} />
      </div>
      <Campo label="Monto">
        <input className={inputCls + " num"} inputMode="decimal" value={valor} onChange={(e) => setValor(e.target.value)} />
      </Campo>
      {deudaDestino > 0 && <Chip onClick={() => setValor(String(deudaDestino))}>Pagar el total: {monto(deudaDestino)}</Chip>}
      <div className="flex flex-col gap-2">
        <span className="text-[13px] font-semibold text-muted">Cuándo</span>
        <FechaChips valor={fecha} onCambio={setFecha} />
      </div>
      {error && <Mensaje>{error}</Mensaje>}
      <Boton
        variante="acento"
        disabled={!origen || !destino || !Number(valor.replace(/\./g, "").replace(",", ".")) || ocupado}
        onClick={async () => {
          const moneda = cuentas?.find((c) => c.id === origen)?.moneda ?? "ARS";
          const ok = await enviar(
            () => api.post("/movimientos", {
              tipo: "transferencia", fecha, moneda, descripcion,
              monto: valor.replace(/\./g, "").replace(",", "."), cuenta_id: origen, cuenta_destino_id: destino,
            }),
            esPago ? "Pago de resumen registrado" : "Transferencia registrada"
          );
          if (ok) { setValor(""); onCerrar(); }
        }}
      >
        {esPago ? "Registrar el pago" : "Registrar la transferencia"}
      </Boton>
    </Sheet>
  );
}
