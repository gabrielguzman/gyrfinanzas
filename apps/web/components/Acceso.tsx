"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const input = "min-h-12 w-full rounded-2xl border border-line-strong bg-ground px-4 py-3 text-base outline-none focus:border-accent";
const boton = "press min-h-12 rounded-2xl bg-accent px-5 font-bold text-accent-ink disabled:opacity-40";
export { input as accesoInput, boton as accesoBoton };

export async function enviarAcceso(ruta: string, datos: object) {
  const r = await fetch(`/api/auth/${ruta}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos) });
  const b = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof b.detail === "string" ? b.detail : "Revisá los datos e intentá de nuevo.");
  return b;
}

export function Acceso({ modo }: { modo: "entrar" | "activar" | "recuperar" | "registro" }) {
  const [usuarios, setUsuarios] = useState<boolean | null>(modo === "entrar" ? null : true);
  const [email, setEmail] = useState("");
  const [nombre, setNombre] = useState("");
  const [password, setPassword] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [ocupado, setOcupado] = useState(false);
  useEffect(() => {
    // Fragmento conservado en memoria, eliminado de la barra y del historial actual.
    const t = new URLSearchParams(window.location.hash.slice(1)).get("token");
    if (t) { setToken(t); window.history.replaceState(null, "", window.location.pathname); }
    if (modo === "entrar") fetch("/api/auth/estado").then(r => { if (!r.ok) throw new Error(); return r.json(); }).then(e => setUsuarios(e.modo === "usuarios")).catch(() => setError("No pude conectar con el servidor. Recargá la página."));
  }, [modo]);
  const nueva = modo === "activar" || (modo === "recuperar" && !!token);
  const titulo = modo === "entrar" ? "Bienvenido de nuevo" : modo === "activar" ? "Creá tu cuenta" : modo === "registro" ? "Empezá con tu email" : token ? "Elegí una contraseña" : "Recuperá tu acceso";
  async function enviar(e: React.FormEvent) {
    e.preventDefault(); setError(""); setMensaje("");
    if (nueva && password !== confirmacion) { setError("Las contraseñas no coinciden."); return; }
    if (modo === "activar" && !token) { setError("Abrí el enlace de verificación o invitación que recibiste."); return; }
    setOcupado(true);
    try {
      if (modo === "entrar") {
        await enviarAcceso("login", { email, password });
        const volver = new URLSearchParams(window.location.search).get("volver");
        window.location.href = volver && volver.startsWith("/") && !volver.startsWith("//") && !volver.startsWith("/\\") ? volver : "/";
      } else if (modo === "activar") {
        await enviarAcceso("aceptar", { token, nombre, password });
        setMensaje("Tu cuenta está lista. Ya podés entrar con tu email y contraseña."); setToken(""); setPassword(""); setConfirmacion("");
      } else if (modo === "registro") {
        const b = await enviarAcceso("registro", { email }); setMensaje(b.mensaje);
      } else if (token) {
        await enviarAcceso("restablecer", { token, password });
        setMensaje("Contraseña actualizada. Se cerraron las sesiones anteriores. Ya podés volver a entrar."); setToken(""); setPassword(""); setConfirmacion("");
      } else {
        const b = await enviarAcceso("recuperar", { email }); setMensaje(b.mensaje);
      }
    } catch (e) { setError(e instanceof TypeError ? "No pude conectar con el servidor." : (e as Error).message); }
    finally { setOcupado(false); }
  }
  return <main className="flex min-h-dvh items-center justify-center bg-ground px-5 py-10">
    <form onSubmit={enviar} className="flex w-full max-w-md flex-col gap-5 rounded-[28px] bg-surface p-7 shadow-soft">
      <img src="/icons/icon-192.png" alt="" width={56} height={56} className="rounded-[16px]" />
      <div><p className="text-sm font-bold text-muted">gyrfinanzas</p><h1 className="display text-[30px] leading-tight font-bold">{titulo}</h1>
        <p className="mt-2 text-sm text-muted">{modo === "registro" ? "Te enviamos un enlace para verificar tu correo. Después elegís tu nombre y contraseña. Tus finanzas serán privadas." : modo === "activar" ? "Tus cuentas y movimientos serán privados." : modo === "entrar" ? usuarios === false ? "Entrá con tu contraseña." : "Entrá con tu email y contraseña." : "Te ayudamos a volver a tus finanzas."}</p></div>
      {!mensaje && <>
        {modo === "activar" && <label className="text-sm font-semibold">Tu nombre<input required maxLength={100} autoComplete="name" value={nombre} onChange={e => setNombre(e.target.value)} className={input + " mt-2"} /></label>}
        {((modo === "entrar" && usuarios !== false) || (modo === "recuperar" && !token) || modo === "registro") && <label className="text-sm font-semibold">Email<input required type="email" autoComplete="email" maxLength={254} value={email} onChange={e => setEmail(e.target.value)} className={input + " mt-2"} /></label>}
        {(modo === "entrar" || nueva) && <label className="text-sm font-semibold">{nueva ? "Nueva contraseña" : "Contraseña"}<input required type="password" minLength={nueva ? 12 : 1} maxLength={200} autoComplete={nueva ? "new-password" : "current-password"} value={password} onChange={e => setPassword(e.target.value)} className={input + " mt-2"} />{nueva && <span className="mt-1 block text-xs text-muted">Usá al menos 12 caracteres. Puede ser una frase.</span>}</label>}
        {nueva && <label className="text-sm font-semibold">Repetí la contraseña<input required type="password" minLength={12} maxLength={200} autoComplete="new-password" value={confirmacion} onChange={e => setConfirmacion(e.target.value)} className={input + " mt-2"} /></label>}
        <button type="submit" disabled={ocupado || usuarios === null} className={boton}>{ocupado ? "Un momento…" : modo === "entrar" ? "Entrar" : modo === "activar" ? "Crear mi cuenta" : modo === "registro" ? "Enviar enlace de registro" : token ? "Guardar contraseña" : "Enviar enlace"}</button>
      </>}
      {error && <p className="rounded-xl bg-danger-soft p-3 text-sm font-semibold text-danger" role="alert">{error}</p>}
      {mensaje && <p className="rounded-xl bg-ground p-3 text-sm" role="status">{mensaje}</p>}
      {modo === "entrar" ? <><Link href="/recuperar" className="text-center text-sm font-bold text-muted">Olvidé mi contraseña</Link><Link href="/registro" className="text-center text-sm font-bold">¿Todavía no tenés cuenta? Registrate</Link></> : <Link href="/entrar" className="text-center text-sm font-bold text-muted">Volver a iniciar sesión</Link>}
    </form>
  </main>;
}
