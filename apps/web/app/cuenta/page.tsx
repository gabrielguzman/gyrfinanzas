"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { accesoInput, accesoBoton, enviarAcceso } from "@/components/Acceso";
import { Salir } from "@/components/Shell";

type Estado = { modo?: string; correo_configurado?: boolean; usuario?: { nombre: string; email: string; administrador: boolean } };
export default function CuentaPage() {
  const [estado, setEstado] = useState<Estado | null>(null);
  const [email, setEmail] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");
  const [enlace, setEnlace] = useState("");
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [repetida, setRepetida] = useState("");
  const [errorClave, setErrorClave] = useState("");
  const [cambiando, setCambiando] = useState(false);
  useEffect(() => { fetch("/api/auth/estado").then(r => r.json()).then(setEstado).catch(() => setError("No pude cargar tu cuenta.")); }, []);
  async function invitar(e: React.FormEvent) {
    e.preventDefault();setOcupado(true);setError("");setMensaje("");setEnlace("");
    try {
      const b = await enviarAcceso("invitar", { email });
      if (b.enviado) setMensaje(`Invitación enviada a ${email}. Vence en 48 horas.`);
      else { setEnlace(b.enlace);setMensaje(`Compartí este enlace en privado con ${email}. Vence en 48 horas y solo se puede usar una vez.`); }
    } catch(e) { setError((e as Error).message); } finally { setOcupado(false); }
  }
  async function cambiar(e: React.FormEvent) {
    e.preventDefault();setErrorClave("");
    if (nueva !== repetida) { setErrorClave("Las contraseñas no coinciden.");return; }
    setCambiando(true);
    try { await enviarAcceso("cambiar-password", { actual, nueva });window.location.href = "/entrar"; }
    catch(e) { setErrorClave((e as Error).message);setCambiando(false); }
  }
  return <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
    <div><h1 className="display text-3xl font-bold">Tu cuenta</h1><p className="mt-2 text-muted">{estado?.usuario?.nombre} {estado?.usuario?.email}</p></div>
    <section className="rounded-[24px] bg-surface p-6 shadow-soft"><h2 className="text-lg font-bold">Tus finanzas son privadas</h2><p className="mt-2 text-sm text-muted">Cada persona tiene sus propias cuentas, movimientos y comprobantes. Las invitaciones crean cuentas independientes.</p>
      <Link href="/recuperar" className="mt-4 inline-block text-sm font-bold">Restablecer mi contraseña →</Link></section>
    {estado?.modo === "usuarios" && <form onSubmit={cambiar} className="flex flex-col gap-4 rounded-[24px] bg-surface p-6 shadow-soft">
      <h2 className="text-lg font-bold">Cambiar contraseña</h2>
      <label className="text-sm font-semibold">Contraseña actual<input required type="password" autoComplete="current-password" maxLength={200} value={actual} onChange={e => setActual(e.target.value)} className={accesoInput + " mt-2"} /></label>
      <label className="text-sm font-semibold">Nueva contraseña<input required type="password" autoComplete="new-password" minLength={12} maxLength={200} value={nueva} onChange={e => setNueva(e.target.value)} className={accesoInput + " mt-2"} /></label>
      <label className="text-sm font-semibold">Repetí la nueva contraseña<input required type="password" autoComplete="new-password" minLength={12} maxLength={200} value={repetida} onChange={e => setRepetida(e.target.value)} className={accesoInput + " mt-2"} /></label>
      <p className="text-xs text-muted">Al menos 12 caracteres. Al guardar se cierran todas tus sesiones y volvés a entrar.</p>
      {errorClave && <p role="alert" className="text-sm text-danger">{errorClave}</p>}
      <button disabled={cambiando} className={accesoBoton}>{cambiando ? "Guardando…" : "Guardar contraseña"}</button>
    </form>}
    {estado?.usuario?.administrador && <form onSubmit={invitar} className="flex flex-col gap-4 rounded-[24px] bg-surface p-6 shadow-soft">
      <div><h2 className="text-lg font-bold">Invitar a una persona</h2><p className="mt-2 text-sm text-muted">{estado.correo_configurado ? "Recibirá un correo para elegir su contraseña." : "El envío de correos está pendiente de configurar. Podés crear un enlace y compartirlo en privado."}</p></div>
      <label className="text-sm font-semibold">Email<input className={accesoInput + " mt-2"} required type="email" autoComplete="off" value={email} onChange={e => setEmail(e.target.value)} /></label>
      <button disabled={ocupado} className={accesoBoton}>{ocupado ? "Creando invitación…" : estado.correo_configurado ? "Enviar invitación" : "Crear enlace de invitación"}</button>
      {mensaje && <p className="text-sm" role="status">{mensaje}</p>}
      {enlace && <label className="text-sm font-semibold">Enlace de invitación<textarea readOnly value={enlace} onFocus={e => e.target.select()} className={accesoInput + " mt-2 break-all"} rows={4} /><button type="button" className="mt-2 text-sm font-bold" onClick={async () => { try { await navigator.clipboard.writeText(enlace);setMensaje("Enlace copiado. Compartilo solo con la persona invitada."); } catch { setMensaje("Seleccioná y copiá el enlace de arriba."); } }}>Copiar enlace</button></label>}
    </form>}
    {error && <p role="alert" className="text-sm text-danger">{error}</p>}
    <div className="lg:hidden"><Salir /></div>
  </div>;
}
