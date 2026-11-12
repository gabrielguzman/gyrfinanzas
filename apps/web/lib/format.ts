import type { Moneda } from "./api";

const nf = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 0 });
const nf2 = new Intl.NumberFormat("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Modo discreto (ver useDiscreto): los montos se muestran como «$ •••••». */
export function discreto(): boolean {
  return typeof document !== "undefined" && document.documentElement.classList.contains("discreto");
}

export function monto(valor: string | number, moneda: Moneda = "ARS", signo?: "+" | "-"): string {
  const n = Math.abs(Number(valor));
  const prefijo = moneda === "USD" ? "USD " : "$ ";
  const s = signo === "+" ? "+ " : signo === "-" ? "− " : Number(valor) < 0 ? "− " : "";
  if (discreto()) return `${s}${prefijo}•••••`;
  const conCentavos = Math.round(n * 100) % 100 !== 0;
  return `${s}${prefijo}${(conCentavos ? nf2 : nf).format(n)}`;
}

const dias = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];

export function hoyISO(): string {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

export function etiquetaDia(iso: string): string {
  const hoy = new Date(hoyISO() + "T00:00:00");
  const d = new Date(iso + "T00:00:00");
  const diff = Math.round((hoy.getTime() - d.getTime()) / 86400000);
  if (diff === 0) return "Hoy";
  if (diff === 1) return "Ayer";
  return `${dias[d.getDay()]} ${d.getDate()}/${d.getMonth() + 1}`;
}

/** Montos grandes abreviados para gráficos: $ 1,2 M · $ 85 mil */
export function compacto(valor: number): string {
  if (discreto()) return "$ •••";
  const n = Math.abs(valor);
  if (n >= 1_000_000) return `$ ${(n / 1_000_000).toLocaleString("es-AR", { maximumFractionDigits: 1 })} M`;
  if (n >= 10_000) return `$ ${Math.round(n / 1000).toLocaleString("es-AR")} mil`;
  return monto(n);
}

export function sumarDias(iso: string, dias: number): string {
  const d = new Date(iso + "T12:00:00");
  d.setDate(d.getDate() + dias);
  return d.toISOString().slice(0, 10);
}

export const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

/** "2026-11" → "noviembre" (o "nov" en corto); agrega el año si no es el actual. */
export function nombrePeriodo(p: string, corto = false): string {
  const [a, m] = p.split("-").map(Number);
  const n = MESES[m - 1];
  const base = corto ? n.slice(0, 3) : n;
  return a === new Date().getFullYear() ? base : `${base} ${corto ? String(a).slice(2) : a}`;
}

export function fechaCorta(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString("es-AR", { day: "numeric", month: "short" });
}

export const nombreMes = (d = new Date()) =>
  d.toLocaleDateString("es-AR", { month: "long", year: "numeric" }).replace(/^\w/, (c) => c.toUpperCase());

export const TIPO_CUENTA: Record<string, string> = {
  banco: "Banco",
  billetera: "Billetera virtual",
  efectivo: "Efectivo",
  tarjeta_credito: "Tarjeta de crédito",
};
export const TIPO_MEDIO: Record<string, string> = {
  debito: "Débito",
  credito: "Crédito",
  transferencia: "Transferencia",
  qr: "QR / billetera",
  efectivo: "Efectivo",
};
