/**
 * Cola offline: si no hay conexión al guardar, el texto queda guardado en el
 * dispositivo y se manda solo cuando vuelve la red.
 */
import { api } from "./api";

const CLAVE = "gyr-cola-captura";
let identidad: string | null = null;

export function vincularCola(id: string, administrador = false) {
  identidad = id;
  const clave = `${CLAVE}:${id}`;
  if (administrador && localStorage.getItem(CLAVE)) {
    // Las cargas previas a las cuentas pertenecen al propietario original.
    const viejas = JSON.parse(localStorage.getItem(CLAVE) || "[]");
    const propias = JSON.parse(localStorage.getItem(clave) || "[]");
    localStorage.setItem(clave, JSON.stringify([...propias, ...viejas]));
    localStorage.removeItem(CLAVE);
  }
}

function claveActual() { return identidad ? `${CLAVE}:${identidad}` : CLAVE; }

interface Pendiente {
  texto: string;
  medio_pago_id: string | null;
  en: number;
}

function leer(): Pendiente[] {
  try {
    return JSON.parse(localStorage.getItem(claveActual()) || "[]");
  } catch {
    return [];
  }
}

function escribir(items: Pendiente[]) {
  try {
    localStorage.setItem(claveActual(), JSON.stringify(items));
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
  if (identidad && identidad !== "local") {
    const estado = await api.get<{ usuario?: { id: string } }>("/auth/estado");
    if (estado.usuario?.id !== identidad) return 0;
  }
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
      restantes.push(it); // nunca perder cargas si la sesión venció o la red falla
    }
  }
  escribir(restantes);
  return enviados;
}
