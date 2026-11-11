import { api, type EstadoAvisos } from "./api";

export type Soporte = "ok" | "inseguro" | "ios_instalar" | "no";

/** ¿Este navegador puede recibir notificaciones? */
export function soporte(): Soporte {
  if (typeof window === "undefined") return "no";
  if (!window.isSecureContext) return "inseguro";
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const instalada = window.matchMedia("(display-mode: standalone)").matches || (navigator as { standalone?: boolean }).standalone;
  if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
    return ios && !instalada ? "ios_instalar" : "no";
  }
  return "ok";
}

function dispositivo(): string {
  const ua = navigator.userAgent;
  if (/iphone/i.test(ua)) return "iPhone";
  if (/ipad/i.test(ua)) return "iPad";
  if (/android/i.test(ua)) return "Android";
  if (/mac os/i.test(ua)) return "Mac";
  if (/windows/i.test(ua)) return "Windows";
  return "Navegador";
}

function bytes(base64url: string): Uint8Array<ArrayBuffer> {
  const relleno = "=".repeat((4 - (base64url.length % 4)) % 4);
  const b64 = (base64url + relleno).replace(/-/g, "+").replace(/_/g, "/");
  const crudo = atob(b64);
  const out = new Uint8Array(new ArrayBuffer(crudo.length));
  for (let i = 0; i < crudo.length; i++) out[i] = crudo.charCodeAt(i);
  return out;
}

async function registro(): Promise<ServiceWorkerRegistration> {
  // En desarrollo el service worker va sin caché (?dev=1); en producción ya lo registra Shell.
  const url = process.env.NODE_ENV === "production" ? "/sw.js" : "/sw.js?dev=1";
  await navigator.serviceWorker.register(url);
  return navigator.serviceWorker.ready;
}

/** La suscripción de ESTE dispositivo, si ya está activa. */
export async function suscripcionActual(): Promise<PushSubscription | null> {
  if (soporte() !== "ok") return null;
  const reg = await navigator.serviceWorker.getRegistration();
  return reg ? reg.pushManager.getSubscription() : null;
}

export async function activar(clavePublica: string): Promise<EstadoAvisos> {
  const permiso = await Notification.requestPermission();
  if (permiso !== "granted") throw new Error(permiso === "denied"
    ? "Las notificaciones están bloqueadas para esta página. Habilitalas en los ajustes del navegador."
    : "No diste permiso para las notificaciones.");
  const reg = await registro();
  let sub = await reg.pushManager.getSubscription();
  if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: bytes(clavePublica) });
  const j = sub.toJSON();
  return api.post<EstadoAvisos>("/avisos/suscribir", { endpoint: j.endpoint, keys: j.keys, dispositivo: dispositivo() });
}

export async function desactivar(): Promise<EstadoAvisos | null> {
  const sub = await suscripcionActual();
  if (!sub) return null;
  const endpoint = sub.endpoint;
  await sub.unsubscribe().catch(() => {});
  return api.post<EstadoAvisos>("/avisos/desuscribir", { endpoint });
}

/** Al cambiar de cuenta, este navegador deja de recibir avisos de la anterior. */
export async function desvincularDispositivo(): Promise<void> {
  const sub = await suscripcionActual();
  if (sub) await sub.unsubscribe();
  const reg = await navigator.serviceWorker?.getRegistration();
  if (reg) for (const n of await reg.getNotifications()) n.close();
}
