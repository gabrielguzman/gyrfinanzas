"use client";

import { useState } from "react";
import useSWR from "swr";
import { Bitcoin, Building2, ChartLine, Landmark, PiggyBank, ScrollText } from "lucide-react";
import { api, ApiError, type Cotizacion, type Inversion, type Moneda, type TipoInversion } from "@/lib/api";
import { fechaCorta, hoyISO, monto } from "@/lib/format";
import { vibrar } from "@/lib/hooks";
import { Sheet } from "./Sheet";
import { useApp } from "./Shell";
import { Boton, Campo, Chip, Mensaje, cx, inputCls } from "./ui";

const num = (s: string) => s.replace(/\./g, "").replace(",", ".").replace(/[^\d.]/g, "");
const miles = (v: string | number | null | undefined) => (v == null || v === "" ? "" : Math.round(Number(v)).toLocaleString("es-AR"));

export const TIPOS: { id: TipoInversion; label: string; Icon: typeof Landmark }[] = [
  { id: "plazo_fijo", label: "Plazo fijo", Icon: Landmark },
  { id: "fci", label: "Fondo (FCI)", Icon: PiggyBank },
  { id: "cripto", label: "Cripto", Icon: Bitcoin },
  { id: "acciones", label: "Acciones / Cedears", Icon: ChartLine },
  { id: "bonos", label: "Bonos / ON", Icon: ScrollText },
  { id: "otro", label: "Otra", Icon: Building2 },
];
export const tipoInv = (t: TipoInversion) => TIPOS.find((x) => x.id === t) ?? TIPOS[5];

export function InversionFila({ i, onAbrir }: { i: Inversion; onAbrir: () => void }) {
  const { Icon } = tipoInv(i.tipo);
  const gan = Number(i.ganancia);
  const pct = Number(i.capital) > 0 ? (gan / Number(i.capital)) * 100 : 0;
  let sub = tipoInv(i.tipo).label;
  if (i.vence) sub += ` · vence ${fechaCorta(i.vence)}`;
  else if (i.actualizado) sub += ` · valor del ${fechaCorta(i.actualizado)}`;
  return (
    <button onClick={onAbrir} className="press flex w-full items-center gap-3 px-4 py-3.5 text-left">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[14px] bg-accent-soft text-accent"><Icon size={19} /></span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-[15px] font-bold">{i.nombre}</span>
        <span className="truncate text-[13px] text-muted">{sub}</span>
      </span>
      <span className="flex shrink-0 flex-col items-end">
        <span className="num font-extrabold">{monto(Number(i.valor) >= 1000 ? Math.round(Number(i.valor)) : i.valor, i.moneda)}</span>
        {gan !== 0 && <span className={cx("num text-xs font-bold", gan > 0 ? "text-ok" : "text-danger")}>{gan > 0 ? "+" : "−"}{Math.abs(pct).toFixed(1).replace(".", ",")}%</span>}
      </span>
    </button>
  );
}

export type InversionAbierta = Inversion | { nueva: true } | null;

export function InversionSheet({ abierta, onCerrar }: { abierta: InversionAbierta; onCerrar: () => void }) {
  const existente = abierta && "id" in abierta ? abierta : undefined;
  return (
    <Sheet abierto={!!abierta} onCerrar={onCerrar} titulo={existente ? existente.nombre : "Nueva inversión"}>
      {abierta && <Form key={existente?.id ?? "nueva"} existente={existente} onListo={onCerrar} />}
    </Sheet>
  );
}

function Form({ existente, onListo }: { existente?: Inversion; onListo: () => void }) {
  const { aviso, refrescar } = useApp();
  const [tipo, setTipo] = useState<TipoInversion>(existente?.tipo ?? "plazo_fijo");
  const [nombre, setNombre] = useState(existente?.nombre ?? "");
  const [moneda, setMoneda] = useState<Moneda>(existente?.moneda ?? "ARS");
  const [capital, setCapital] = useState(miles(existente?.capital));
  const [tna, setTna] = useState(existente?.tna ? String(Number(existente.tna)).replace(".", ",") : "");
  const [inicio, setInicio] = useState(existente?.fecha_inicio ?? hoyISO());
  const [vence, setVence] = useState(existente?.vence ?? "");
  const [valor, setValor] = useState(miles(existente?.valor_actual));
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const conTasa = tipo === "plazo_fijo";
  const conValor = !conTasa;

  async function guardar() {
    setOcupado(true);
    setError(null);
    const tasa = tna ? tna.replace(",", ".") : null;
    try {
      if (existente) {
        await api.patch(`/inversiones/${existente.id}`, {
          nombre: nombre.trim(), capital: num(capital), tna: conTasa ? tasa : null, vence: vence || null,
          ...(conValor ? { valor_actual: num(valor) || null } : {}),
        });
      } else {
        await api.post("/inversiones", {
          nombre: nombre.trim() || tipoInv(tipo).label, tipo, moneda, capital: num(capital), tna: conTasa ? tasa : null,
          fecha_inicio: inicio, vence: vence || null, valor_actual: conValor && num(valor) ? num(valor) : null,
        });
      }
      vibrar();
      refrescar();
      aviso(existente ? "Actualizada" : "Inversión agregada");
      onListo();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No pude conectar con el servidor");
    } finally {
      setOcupado(false);
    }
  }

  async function cerrar() {
    if (!existente) return;
    await api.patch(`/inversiones/${existente.id}`, { cerrada: true });
    refrescar();
    aviso(`${existente.nombre}: cerrada`, { deshacer: () => api.patch(`/inversiones/${existente.id}`, { cerrada: false }) });
    onListo();
  }

  return (
    <div className="flex flex-col gap-4">
      {existente ? (
        <div className="grid grid-cols-2 gap-2.5 text-sm">
          <div className="rounded-2xl bg-surface p-3"><p className="text-muted">Vale hoy</p><p className="num font-bold">{monto(existente.valor, existente.moneda)}</p></div>
          <div className="rounded-2xl bg-surface p-3">
            <p className="text-muted">Ganancia</p>
            <p className={cx("num font-bold", Number(existente.ganancia) > 0 ? "text-ok" : Number(existente.ganancia) < 0 && "text-danger")}>
              {monto(Math.abs(Number(existente.ganancia)), existente.moneda, Number(existente.ganancia) >= 0 ? "+" : "-")}
            </p>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Tipo">
          {TIPOS.map((t) => <Chip key={t.id} activo={tipo === t.id} onClick={() => setTipo(t.id)}><t.Icon size={14} /> {t.label}</Chip>)}
        </div>
      )}

      {conValor && existente && (
        <Campo label="Cuánto vale hoy" ayuda="Fijate en la app del banco o del exchange y actualizalo de vez en cuando.">
          <input className={inputCls + " num text-lg"} inputMode="decimal" value={valor} onChange={(e) => setValor(miles(num(e.target.value)))} autoFocus />
        </Campo>
      )}

      <Campo label="Nombre">
        <input className={inputCls} value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder={tipo === "plazo_fijo" ? "Plazo fijo Galicia" : tipo === "cripto" ? "Bitcoin" : "FCI Mercado Pago"} />
      </Campo>
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-end gap-2">
        <Campo label={conTasa ? "Cuánto pusiste" : "Cuánto invertiste"}>
          <input className={inputCls + " num"} inputMode="numeric" value={capital} onChange={(e) => setCapital(miles(num(e.target.value)))} />
        </Campo>
        {!existente && (
          <div className="flex gap-1 pb-0.5" role="radiogroup" aria-label="Moneda">
            <Chip activo={moneda === "ARS"} onClick={() => setMoneda("ARS")}>$</Chip>
            <Chip activo={moneda === "USD"} onClick={() => setMoneda("USD")}>USD</Chip>
          </div>
        )}
      </div>
      {conTasa && (
        <div className="grid grid-cols-2 gap-3">
          <Campo label="TNA %"><input className={inputCls + " num"} inputMode="decimal" value={tna} onChange={(e) => setTna(e.target.value.replace(/[^\d,]/g, ""))} placeholder="32" /></Campo>
          <Campo label="Vence"><input type="date" className={inputCls} value={vence} min={inicio} onChange={(e) => setVence(e.target.value)} /></Campo>
        </div>
      )}
      {!existente && (
        <div className="grid grid-cols-2 gap-3">
          <Campo label="Desde"><input type="date" className={inputCls} value={inicio} max={hoyISO()} onChange={(e) => e.target.value && setInicio(e.target.value)} /></Campo>
          {conValor && <Campo label="Vale hoy (opcional)"><input className={inputCls + " num"} inputMode="numeric" value={valor} onChange={(e) => setValor(miles(num(e.target.value)))} /></Campo>}
        </div>
      )}
      {conTasa && <p className="text-xs text-faint">Los intereses se calculan solos con la TNA. Te aviso unos días antes de que venza.</p>}
      {error && <Mensaje>{error}</Mensaje>}
      <Boton variante="acento" disabled={ocupado || !Number(num(capital))} onClick={guardar}>{existente ? "Guardar" : "Agregar"}</Boton>
      {existente && (
        <div className="flex gap-5 text-sm">
          <button className="font-bold text-muted" onClick={cerrar}>La saqué (cerrar)</button>
          <button className="font-bold text-danger" onClick={async () => { await api.del(`/inversiones/${existente.id}`); refrescar(); aviso("Borrada"); onListo(); }}>Borrar</button>
        </div>
      )}
    </div>
  );
}

/** Qué dólar usar para pasar a pesos. */
export function SelectorCotizacion({ c }: { c: Cotizacion }) {
  const { refrescar } = useApp();
  const { mutate } = useSWR<Cotizacion>("/cotizacion");
  const [manual, setManual] = useState(c.manual && c.valor ? miles(c.valor) : "");
  async function elegir(datos: Record<string, unknown>) {
    const r = await api.put<Cotizacion>("/cotizacion", datos);
    await mutate(r, { revalidate: false });
    refrescar();
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Cotización del dólar">
        {Object.entries(c.casas).filter(([k]) => ["bolsa", "oficial", "blue", "cripto"].includes(k)).map(([k, v]) => (
          <Chip key={k} activo={!c.manual && c.casa === k} onClick={() => { setManual(""); elegir({ casa: k, borrar_manual: true }); }}>{v}</Chip>
        ))}
      </div>
      <label className="flex items-center gap-2 text-sm font-semibold whitespace-nowrap">
        O a mano: $
        <input className={inputCls + " num w-32"} inputMode="numeric" value={manual} placeholder="1.200"
          onChange={(e) => setManual(miles(num(e.target.value)))}
          onBlur={() => num(manual) ? elegir({ manual: num(manual) }) : c.manual && elegir({ borrar_manual: true })} />
      </label>
    </div>
  );
}
