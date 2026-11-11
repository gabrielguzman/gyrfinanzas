/**
 * Cola offline: si no hay conexión al guardar, el texto queda guardado en el
 * dispositivo y se manda solo cuando vuelve la red.
 */
import { api } from "./api";

const CLAVE = "gyr-cola-captura";

interface Pendiente {
  texto: string;
  medio_pago_id: string | null;
  en: number;
}

function leer(): Pendiente[] {
  try {
    return JSON.parse(localStorage.getItem(CLAVE) || "[]");
  } catch {
    return [];
  }
}

function escribir(items: Pendiente[]) {
  try {
    localStorage.setItem(CLAVE, JSON.stringify(items));
  } catch {
    /* almacenamiento no disponible */
  }
}

export function encolar(texto: string, medio_pago_id: string | null) {
  escribir([...leer(), { texto, medio_pago_id, en: Date.now() }]);
}

export function cantidadEnCola(): number {
  return leer().length;
}

/** Manda lo encolado a la bandeja. Devuelve cuántos se enviaron. */
export async function vaciarCola(): Promise<number> {
  const items = leer();
  if (!items.length) return 0;
  const restantes: Pendiente[] = [];
  let enviados = 0;
  for (const it of items) {
    try {
      const mov = await api.post<{ id: string }>("/captura", { texto: it.texto });
      if (it.medio_pago_id) await api.patch(`/movimientos/${mov.id}`, { medio_pago_id: it.medio_pago_id });
      enviados++;
    } catch (e) {
      if (e instanceof TypeError) restantes.push(it); // sigue sin red
    }
  }
  escribir(restantes);
  return enviados;
}
