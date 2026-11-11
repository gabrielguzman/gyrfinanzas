"use client";

import { useState } from "react";
import { Lock } from "lucide-react";

export default function EntrarPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  async function entrar(e: React.FormEvent) {
    e.preventDefault();
    setOcupado(true);
    setError(null);
    try {
      const r = await fetch("/api/auth/login", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ password }),
      });
      if (r.ok) {
        const volver = new URLSearchParams(window.location.search).get("volver");
        window.location.href = volver && volver.startsWith("/") && !volver.startsWith("//") ? volver : "/";
        return;
      }
      const b = await r.json().catch(() => ({}));
      setError(typeof b.detail === "string" ? b.detail : "No pude entrar");
    } catch {
      setError("No pude conectar con el servidor");
    } finally {
      setOcupado(false);
    }
  }

  return (
    <main className="flex min-h-dvh items-center justify-center bg-ground px-5">
      <form onSubmit={entrar} className="flex w-full max-w-sm flex-col gap-5 rounded-[28px] bg-surface p-7 shadow-soft">
        <img src="/icons/icon-192.png" alt="" width={56} height={56} className="rounded-[16px]" />
        <div>
          <h1 className="display text-[32px] leading-tight font-bold">gyrfinanzas</h1>
          <p className="text-sm text-muted">Entrá con tu contraseña.</p>
        </div>
        <label className="flex min-h-12 items-center gap-3 rounded-2xl border border-line-strong bg-ground px-4 focus-within:border-accent">
          <Lock size={18} className="text-faint" aria-hidden />
          <span className="sr-only">Contraseña</span>
          <input
            type="password" autoComplete="current-password" autoFocus value={password}
            onChange={(e) => setPassword(e.target.value)} className="w-full bg-transparent py-3 text-base outline-none"
          />
        </label>
        {error && <p className="rounded-xl bg-danger-soft p-3 text-sm font-semibold text-danger" role="alert">{error}</p>}
        <button type="submit" disabled={ocupado || !password} className="press min-h-12 rounded-2xl bg-accent font-bold text-accent-ink disabled:opacity-40">
          Entrar
        </button>
      </form>
    </main>
  );
}
