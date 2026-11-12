export type Moneda = "ARS" | "USD";
export type TipoCuenta = "banco" | "billetera" | "efectivo" | "tarjeta_credito";
export type TipoMedio = "debito" | "credito" | "transferencia" | "qr" | "efectivo";
export type TipoMov = "gasto" | "ingreso" | "transferencia";
export type Rol = "ticket" | "factura" | "garantia" | "resumen" | "otro";

export interface Cuenta {
  id: string;
  nombre: string;
  tipo: TipoCuenta;
  moneda: Moneda;
  saldo_inicial: string;
  saldo: string;
  dia_cierre: number | null;
  dia_vencimiento: number | null;
  archivada: boolean;
}
export interface MedioPago {
  id: string;
  nombre: string;
  tipo: TipoMedio;
  cuenta_id: string;
  alias: string;
  archivado: boolean;
}
export interface Categoria {
  id: string;
  nombre: string;
  tipo: "gasto" | "ingreso";
  palabras: string;
  icono: string;
  color: string;
}
export interface Adjunto {
  archivo_id: string;
  nombre: string;
  mime: string;
  rol: Rol;
}
export interface Movimiento {
  id: string;
  tipo: TipoMov;
  estado: "pendiente" | "confirmado";
  origen: string;
  fecha: string;
  monto: string;
  moneda: Moneda;
  descripcion: string;
  texto_original: string | null;
  categoria_id: string | null;
  categoria: string | null;
  categoria_icono: string | null;
  categoria_color: string | null;
  medio_pago_id: string | null;
  medio_pago: string | null;
  cuenta_id: string | null;
  cuenta: string | null;
  cuenta_destino_id: string | null;
  cuenta_destino: string | null;
  adjuntos: Adjunto[];
  tiene_comprobante: boolean;
  valio: boolean | null;
  deuda_id: string | null;
  cuotas: number | null;
  fijo_id: string | null;
  etiquetas: string[];
  garantia: { id: string; vence: string; estado: EstadoGarantia; dias_restantes: number } | null;
  creado: string;
}
export interface Interpretacion {
  etiquetas: string[];
  tipo: TipoMov;
  monto: string | null;
  moneda: Moneda;
  descripcion: string;
  fecha: string;
  medio_pago_id: string | null;
  medio_pago: string | null;
  cuenta_id: string | null;
  categoria_id: string | null;
  categoria: string | null;
  cuotas: number | null;
  categoria_icono: string | null;
  categoria_color: string | null;
  partes: { inicio: number; fin: number; tipo: string }[];
  deuda_tipo: string | null;
  deuda_nombre: string | null;
  garantia_meses: number | null;
  aviso: string | null;
  motivo_medio: string | null;
  faltantes: string[];
}
export interface Frecuente {
  texto: string;
  descripcion: string;
  monto: string;
  medio_pago: string | null;
  categoria_icono: string | null;
  categoria_color: string | null;
  veces: number;
}
export interface CategoriaTotal {
  categoria_id: string | null;
  nombre: string;
  icono: string;
  color: string;
  total: string;
  cantidad: number;
}
export interface Resumen {
  mes: string;
  dias_mes: number;
  dia_hoy: number | null;
  gastos: string;
  ingresos: string;
  gastos_anterior_a_la_fecha: string;
  gastos_anterior_total: string;
  por_categoria: CategoriaTotal[];
  diario: { dia: number; acumulado: string }[];
  diario_anterior: { dia: number; acumulado: string }[];
}
export interface Archivo {
  id: string;
  nombre_original: string;
  mime: string;
  tamano: number;
  creado: string;
  movimientos: string[];
  garantia?: string | null;
}
export interface Inicio {
  totales: { moneda: Moneda; en_cuentas: string; deuda_tarjetas: string; cuotas_futuras?: string; disponible: string }[];
  pendientes: number;
  sin_comprobante_mes: number;
}

export interface Plan {
  id: string;
  cuenta_id: string;
  descripcion: string;
  monto_cuota: string;
  cuotas_total: number;
  primer_periodo: string;
  moneda: Moneda;
  cuota_actual: number | null;
  restantes: number;
  ultimo_periodo: string;
  movimiento_id: string | null;
}
export interface ResumenCorto {
  id: string;
  periodo: string | null;
  estado: "procesando" | "revision" | "confirmado" | "error";
  fecha_cierre: string | null;
  fecha_vencimiento: string | null;
  total_ars: string | null;
  total_usd: string | null;
  pago_minimo: string | null;
  tna: string | null;
  interes_si_minimo: string | null;
}
export interface Tarjeta {
  cuenta_id: string;
  nombre: string;
  deuda: string;
  dia_cierre: number | null;
  dia_vencimiento: number | null;
  proximo_periodo: string;
  mejor_dia_compra: string;
  ultimo_resumen: ResumenCorto | null;
  pendiente_revision: string | null;
  planes: Plan[];
  compromisos: { periodo: string; total: string; planes: number }[];
  liberacion: { periodo: string; monto: string; planes_que_terminan: number } | null;
}
export type TipoLinea = "consumo" | "cuota" | "impuesto" | "interes" | "cargo" | "pago" | "ajuste";
export interface LineaResumen {
  id: string;
  fecha: string | null;
  descripcion: string;
  monto: string;
  moneda: Moneda;
  tipo: TipoLinea;
  cuota_n: number | null;
  cuota_total: number | null;
  accion: "vincular" | "crear" | "ignorar";
  movimiento_id: string | null;
  movimiento: string | null;
  plan_id: string | null;
}
export interface ResumenTarjeta extends ResumenCorto {
  cuenta_id: string;
  cuenta: string;
  metodo: string;
  error: string | null;
  saldo_anterior: string | null;
  archivo_id: string | null;
  verificacion: {
    saldo_anterior: string;
    cargos: string;
    pagos_y_ajustes: string;
    calculado: string;
    total: string | null;
    diferencia: string | null;
    cuadra: boolean;
    por_tipo: Record<TipoLinea, string>;
  } | null;
  lineas: LineaResumen[];
}

export type TipoDeuda = "prestamo" | "debo" | "me_deben";
export interface Deuda {
  id: string;
  tipo: TipoDeuda;
  nombre: string;
  moneda: Moneda;
  monto_inicial: string;
  fecha_alta: string;
  tna: string | null;
  indexacion: "fija" | "uva";
  cuota: string | null;
  cuotas_total: number | null;
  dia_vencimiento: number | null;
  cuenta_id: string | null;
  cerrada: boolean;
  notas: string;
  saldo: string;
  pagado: string;
  intereses_pagados: string;
  pagos: number;
  cuotas_pagadas: number | null;
  cuotas_restantes: number | null;
  proximo_vencimiento: string | null;
  cuota_sugerida: string | null;
}
export interface DeudaDetalle extends Deuda {
  movimientos: Movimiento[];
}
export interface Estrategia {
  estrategia: "avalancha" | "bola_de_nieve";
  meses: number | null;
  fecha_fin: string | null;
  intereses: string;
  orden: { id: string; nombre: string; mes: number; fecha: string }[];
  serie: string[];
}
export interface Simulacion {
  deudas: { id: string; nombre: string; tipo: string; saldo: string; tasa_anual: string; tasa_real_anual: string | null; minimo: string }[];
  presupuesto_mensual: string;
  avalancha: Estrategia;
  bola_de_nieve: Estrategia;
}

export interface Hallazgo {
  clave: string;
  tipo: "suscripcion_aumento" | "fijos" | "hormiga" | "plata_tirada" | "duplicado" | "desvio" | "garantia" | "sin_garantia" | "meta" | "inversion";
  tono: "aviso" | "info";
  titulo: string;
  detalle: string;
  monto: string | null;
  accion: { tipo: "categoria" | "movimiento" | "buscar" | "garantia" | "garantia_nueva" | "link"; valor: string } | null;
  movimientos: string[];
}
export interface Arrepentimiento {
  categoria: string;
  respondidos: number;
  no: number;
}
export interface Semana {
  desde: string;
  hasta: string;
  gastos: string;
  gastos_anterior: string;
  cantidad: number;
  fijos: string;
  variables: string;
  variables_anterior: string;
  top: { nombre: string; icono: string; color: string; total: string }[];
  mayor: { descripcion: string; monto: string; fecha: string } | null;
  pendientes: number;
  vencimientos: { fecha: string; que: string; monto: string }[];
  hallazgos: Hallazgo[];
  repaso: Movimiento[];
  arrepentimientos: Arrepentimiento[];
}

export type EstadoGarantia = "vigente" | "por_vencer" | "vencida" | "en_reparacion";
export interface Garantia {
  id: string;
  producto: string;
  comercio: string;
  serie: string;
  fecha_compra: string;
  meses: number;
  vence: string;
  estado: EstadoGarantia;
  dias_restantes: number;
  progreso: number;
  en_reparacion_desde: string | null;
  dias_reparacion: number;
  notas: string;
  movimiento_id: string | null;
  monto: string | null;
  medio_pago: string | null;
  archivos: { id: string; nombre: string; mime: string; rol: string }[];
}

export interface Presupuesto {
  configurado: boolean;
  dia_cobro: number | null;
  ingreso_esperado: string | null;
  cobro_detectado: boolean;
  ahorro: string;
  desde: string | null;
  hasta: string | null;
  proximo_cobro: string | null;
  dias_restantes: number;
  dias_total: number;
  ingreso: string;
  fijos: string;
  cuotas_tarjetas: string;
  cuotas_prestamos: string;
  metas: string;
  para_gastar: string;
  gastado: string;
  gastado_hoy: string;
  restante: string;
  por_dia: string;
  hoy: string;
  manana: string | null;
  proyeccion_fin: string | null;
  estado: "bien" | "justo" | "pasado" | "sin_datos";
  detalle_fijos: { nombre: string; monto: string }[];
  detalle_cuotas: { nombre: string; monto: string }[];
  detalle_metas: { nombre: string; monto: string }[];
}
export interface EventoPlan {
  fecha: string;
  tipo: "cobro" | "tarjeta" | "prestamo" | "fijo";
  titulo: string;
  monto: string;
  estimado: boolean;
}
export interface CalendarioPlan {
  saldo_hoy: string;
  gasto_diario: string;
  eventos: EventoPlan[];
  serie: { fecha: string; saldo: string }[];
  rojo: { fecha: string; saldo: string } | null;
  minimo: { fecha: string; saldo: string };
}

export interface Meta {
  id: string;
  nombre: string;
  emoji: string;
  objetivo: string;
  moneda: Moneda;
  fecha_objetivo: string | null;
  aporte_mensual: string | null;
  cuenta_id: string | null;
  cuenta: string | null;
  ahorrado: string;
  falta: string;
  progreso: number;
  cumplida: boolean;
  por_mes: string | null;
  por_mes_ars: string | null;
  meses_restantes: number | null;
  fecha_estimada: string | null;
  ritmo: string | null;
  en_camino: boolean | null;
  aportes: { id: string; fecha: string; monto: string; nota: string }[];
}
export type TipoInversion = "plazo_fijo" | "fci" | "cripto" | "acciones" | "bonos" | "otro";
export interface Inversion {
  id: string;
  nombre: string;
  tipo: TipoInversion;
  moneda: Moneda;
  capital: string;
  tna: string | null;
  fecha_inicio: string;
  vence: string | null;
  valor_actual: string | null;
  actualizado: string | null;
  cerrada: boolean;
  notas: string;
  valor: string;
  ganancia: string;
  valor_ars: string | null;
}
export interface Cotizacion {
  valor: string | null;
  casa: string;
  nombre: string;
  fecha: string | null;
  vieja: boolean;
  manual: boolean;
  casas: Record<string, string>;
}
export interface Patrimonio {
  items: { grupo: string; nombre: string; moneda: Moneda; monto: string; ars: string | null; activo: boolean; ref: string }[];
  activos: string;
  pasivos: string;
  neto: string;
  neto_usd: string | null;
  cotizacion: Cotizacion;
  sin_convertir: boolean;
  liquido: string;
  gasto_esencial: string;
  gasto_mensual: string;
  meses_esencial: string | null;
  meses_total: string | null;
  serie: { fecha: string; neto: string; estimado: boolean }[];
}

export interface Fijo {
  id: string;
  nombre: string;
  clave: string;
  monto: string;
  dia: number;
  cada_meses: number;
  mes_inicio: number | null;
  por_mes: string;
  activo: boolean;
  categoria_id: string | null;
  categoria: string | null;
  categoria_icono: string | null;
  categoria_color: string | null;
  medio_pago_id: string | null;
  medio_pago: string | null;
  proxima: string;
  este_mes: "pagado" | "en_bandeja" | "por_venir";
  movimiento_id: string | null;
}
export interface FijoSugerido {
  clave: string;
  nombre: string;
  monto: string;
  dia: number;
  meses: number;
  categoria: string | null;
}
export interface Fijos {
  fijos: Fijo[];
  sugeridos: FijoSugerido[];
  total_mensual: string;
  este_mes_total: string;
  pagado_mes: string;
}
export interface Regla {
  id: string;
  texto: string;
  categoria_id: string;
  categoria: string;
  categoria_icono: string;
  categoria_color: string;
}
export interface PreviaRegla {
  texto: string;
  total: number;
  a_cambiar: number;
  ejemplos: string[];
}
export interface SugerenciaRegla {
  texto: string | null;
  total: number;
  a_cambiar: number;
  existe: boolean;
}
export interface PrefsAvisos {
  notif_hoy: boolean;
  notif_fijos: boolean;
  notif_vencimientos: boolean;
  notif_avisos: boolean;
  notif_racha: boolean;
  notif_hora: string;
}
export interface EstadoAvisos {
  clave_publica: string;
  dispositivos: number;
  preferencias: PrefsAvisos;
}

export interface EtiquetaResumen {
  id: string;
  nombre: string;
  total: string;
  total_usd: string;
  cantidad: number;
  desde: string | null;
  hasta: string | null;
  activa: boolean;
  por_categoria: { nombre: string; icono: string; color: string; total: string }[];
}
export interface Etiquetas {
  activa: string | null;
  etiquetas: EtiquetaResumen[];
}
export interface Racha {
  actual: number;
  mejor: number;
  hoy: "cargado" | "sin_gastos" | "vacio";
  dias: { fecha: string; estado: "cargado" | "sin_gastos" | "vacio" }[];
}

export function apiBase(): string {
  // Por defecto, la API se alcanza a través de la propia web (ver next.config.ts).
  return process.env.NEXT_PUBLIC_API_URL || "/api";
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  // La pestaña conserva su identidad: si otra pestaña cambia de cuenta, la API
  // rechaza una escritura antigua en vez de aplicarla al usuario nuevo.
  if (typeof window !== "undefined" && !path.startsWith("/auth")) {
    const id = sessionStorage.getItem("gyr-identidad");
    if (id && id !== "local") headers.set("X-Gyr-Usuario", id);
  }
  const res = await fetch(`${apiBase()}${path}`, { credentials: "same-origin", ...init, headers });
  if (res.status === 409 && res.headers.get("X-Gyr-Cambio-Cuenta")) window.location.reload();
  if (res.status === 401 && !path.startsWith("/auth") && typeof window !== "undefined" && window.location.pathname !== "/entrar") {
    window.location.href = `/entrar?volver=${encodeURIComponent(window.location.pathname)}`;
  }
  if (!res.ok) {
    let detalle = `Error ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detalle = body.detail;
      else if (Array.isArray(body.detail)) detalle = body.detail.map((d: { msg: string }) => d.msg).join(", ");
    } catch {
      /* respuesta sin JSON */
    }
    throw new ApiError(res.status, detalle);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const fetcher = <T,>(path: string) => request<T>(path);

export const api = {
  get: <T,>(path: string) => request<T>(path),
  post: <T,>(path: string, body?: unknown) => request<T>(path, json("POST", body)),
  patch: <T,>(path: string, body: unknown) => request<T>(path, json("PATCH", body)),
  put: <T,>(path: string, body: unknown) => request<T>(path, json("PUT", body)),
  del: <T,>(path: string) => request<T>(path, { method: "DELETE" }),
  subir: <T,>(path: string, archivo: File, extra: Record<string, string> = {}) => {
    const fd = new FormData();
    fd.append("archivo", archivo);
    Object.entries(extra).forEach(([k, v]) => fd.append(k, v));
    return request<T>(path, { method: "POST", body: fd });
  },
  urlArchivo: (id: string) => `${apiBase()}/archivos/${id}/contenido`,
};
