"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { CalendarRange, FileText, HandCoins, Home, List, Monitor, Moon, Goal, Landmark, LogOut, Plus, ShieldCheck, ShoppingBag, Sun, Target, Wallet } from "lucide-react";
import { SWRConfig, useSWRConfig } from "swr";
import { fetcher } from "@/lib/api";
import { vaciarCola } from "@/lib/cola";
import { useTema, type Tema } from "@/lib/hooks";
import { CapturaSheet } from "./CapturaSheet";
import { GarantiaSheet, type GarantiaAbierta } from "./Garantias";
import { MovimientoSheet } from "./MovimientoSheet";
import { cx } from "./ui";

interface Aviso {
  id: number;
  texto: string;
  deshacer?: () => unknown;
}
interface Ctx {
  abrirCaptura: () => void;
  abrirMovimiento: (id: string) => void;
  /** Abre una garantía por id, o el alta (opcionalmente desde un gasto). */
  abrirGarantia: (g: { id: string } | { nueva: true; movimiento?: string }) => void;
  aviso: (texto: string, opciones?: { deshacer?: () => unknown }) => void;
  refrescar: () => void;
}
const AppCtx = createContext<Ctx | null>(null);

export function useApp(): Ctx {
  const c = useContext(AppCtx);
  if (!c) throw new Error("useApp fuera de Shell");
  return c;
}

const NAV = [
  { href: "/", label: "Inicio", Icon: Home },
  { href: "/plan", label: "Hasta el cobro", Icon: Target },
  { href: "/comprar", label: "¿Me lo compro?", Icon: ShoppingBag },
  { href: "/movimientos", label: "Movimientos", Icon: List },
  { href: "/cuentas", label: "Cuentas", Icon: Wallet },
  { href: "/deudas", label: "Deudas", Icon: HandCoins },
  { href: "/metas", label: "Metas", Icon: Goal },
  { href: "/patrimonio", label: "Patrimonio", Icon: Landmark },
  { href: "/semana", label: "Tu semana", Icon: CalendarRange },
  { href: "/comprobantes", label: "Comprobantes", Icon: FileText },
  { href: "/garantias", label: "Garantías", Icon: ShieldCheck },
] as const;
// En el celu entran cuatro: Comprobantes y Garantías se abren desde Movimientos, Tu semana desde Inicio.
// El plan se abre desde la tarjeta «Hoy podés gastar» de Inicio.
// Metas y Patrimonio, desde Cuentas e Inicio.
const NAV_CELU = NAV.filter((n) => !["/comprobantes", "/semana", "/garantias", "/plan", "/metas", "/patrimonio", "/comprar"].includes(n.href));

function activa(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname.startsWith(href) || (href === "/cuentas" && pathname.startsWith("/tarjetas"));
}

const TEMAS: { id: Tema; label: string; Icon: typeof Sun }[] = [
  { id: "system", label: "Automático", Icon: Monitor },
  { id: "light", label: "Claro", Icon: Sun },
  { id: "dark", label: "Oscuro", Icon: Moon },
];

function SelectorTema({ compacto }: { compacto?: boolean }) {
  const [tema, setTema] = useTema();
  return (
    <div role="radiogroup" aria-label="Tema" className={cx("flex rounded-full bg-surface-2 p-1", compacto ? "gap-0.5" : "gap-1")}>
      {TEMAS.map(({ id, label, Icon }) => (
        <button
          key={id}
          role="radio"
          aria-checked={tema === id}
          aria-label={label}
          title={label}
          onClick={() => setTema(id)}
          className={cx(
            "press flex h-9 flex-1 items-center justify-center gap-1.5 rounded-full px-2.5 text-xs font-bold",
            tema === id ? "bg-surface text-ink shadow-soft" : "text-muted"
          )}
        >
          <Icon size={15} />
          {!compacto && <span>{label}</span>}
        </button>
      ))}
    </div>
  );
}

function Interior({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { mutate } = useSWRConfig();
  const [captura, setCaptura] = useState(false);
  const [movId, setMovId] = useState<string | null>(null);
  const [garantia, setGarantia] = useState<GarantiaAbierta>(null);
  const [toast, setToast] = useState<Aviso | null>(null);
  const timer = useRef<number | undefined>(undefined);

  const refrescar = useCallback(() => {
    mutate(() => true);
  }, [mutate]);

  const aviso = useCallback((texto: string, opciones?: { deshacer?: () => unknown }) => {
    window.clearTimeout(timer.current);
    const nuevo = { id: Date.now(), texto, deshacer: opciones?.deshacer };
    setToast(nuevo);
    timer.current = window.setTimeout(() => setToast((t) => (t?.id === nuevo.id ? null : t)), opciones?.deshacer ? 5000 : 2800);
  }, []);

  useEffect(() => {
    if (process.env.NODE_ENV === "production" && "serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
    if (new URLSearchParams(window.location.search).get("cargar")) setCaptura(true);
    const sincronizar = async () => {
      const n = await vaciarCola();
      if (n) {
        aviso(`Se enviaron ${n} cargas hechas sin conexión`);
        refrescar();
      }
    };
    sincronizar();
    window.addEventListener("online", sincronizar);
    return () => window.removeEventListener("online", sincronizar);
  }, [aviso, refrescar]);

  // Atajo de teclado en la compu: «n» abre la carga.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.key === "n" && !e.metaKey && !e.ctrlKey && !["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName)) {
        e.preventDefault();
        setCaptura(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const ctx: Ctx = { abrirCaptura: () => setCaptura(true), abrirMovimiento: setMovId, abrirGarantia: setGarantia, aviso, refrescar };

  return (
    <AppCtx.Provider value={ctx}>
      <div className="lg:flex">
        {/* Menú lateral (compu) */}
        <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 flex-col gap-6 border-r border-line px-5 py-7 lg:flex">
          <Link href="/" className="display flex items-center gap-2.5 px-2 text-[22px] font-bold">
            <img src="/icons/icon-192.png" alt="" width={30} height={30} className="rounded-[9px]" />
            gyrfinanzas
          </Link>
          <button
            onClick={() => setCaptura(true)}
            className="press flex min-h-12 items-center justify-between rounded-2xl bg-accent px-4 font-bold text-accent-ink"
          >
            <span className="flex items-center gap-2">
              <Plus size={20} strokeWidth={2.6} /> Cargar
            </span>
            <kbd className="rounded-md bg-white/20 px-1.5 text-xs font-bold">N</kbd>
          </button>
          <nav className="flex flex-col gap-1">
            {NAV.map(({ href, label, Icon }) => (
              <Link
                key={href}
                href={href}
                aria-current={activa(pathname, href) ? "page" : undefined}
                className={cx(
                  "press flex min-h-11 items-center gap-3 rounded-xl px-3 text-[15px] font-bold",
                  activa(pathname, href) ? "bg-surface text-ink shadow-soft" : "text-muted hover:bg-surface-2"
                )}
              >
                <Icon size={19} />
                {label}
              </Link>
            ))}
          </nav>
          <div className="mt-auto"><Salir /></div>
          <div className="flex items-center justify-between gap-2 px-2">
            <span className="text-xs font-semibold text-faint">Tema</span>
            <SelectorTema compacto />
          </div>
        </aside>

        <main className="mx-auto w-full max-w-md px-5 pt-6 pb-32 lg:max-w-6xl lg:px-10 lg:pt-10 lg:pb-16">{children}</main>
      </div>

      {/* Barra inferior (celu) */}
      <nav className="safe-bottom fixed inset-x-0 bottom-0 z-40 border-t border-line bg-surface/95 backdrop-blur lg:hidden">
        <div className="mx-auto grid h-[72px] max-w-md grid-cols-5 items-start pt-2">
          {NAV_CELU.slice(0, 2).map(({ href, label, Icon }) => (
            <TabLink key={href} href={href} label={label} activo={activa(pathname, href)} Icon={Icon} />
          ))}
          <div className="flex justify-center">
            <button
              onClick={() => setCaptura(true)}
              aria-label="Cargar algo"
              className="press -mt-7 flex h-[60px] w-[60px] items-center justify-center rounded-[22px] border-4 border-ground bg-accent text-accent-ink shadow-soft"
            >
              <Plus size={28} strokeWidth={2.6} />
            </button>
          </div>
          {NAV_CELU.slice(2).map((n) => (
            <TabLink key={n.href} href={n.href} label={n.label} activo={activa(pathname, n.href)} Icon={n.Icon} />
          ))}
        </div>
      </nav>

      <CapturaSheet abierto={captura} onCerrar={() => setCaptura(false)} />
      <MovimientoSheet id={movId} onCerrar={() => setMovId(null)} />
      <GarantiaSheet abierta={garantia} onCerrar={() => setGarantia(null)} />

      {toast && (
        <div key={toast.id} className="anim-aparecer fixed inset-x-0 bottom-24 z-[60] flex justify-center px-5 lg:bottom-8" role="status">
          <div className="flex items-center gap-4 rounded-2xl bg-ink py-2.5 pr-2.5 pl-4 text-sm font-semibold text-ground shadow-soft">
            <span>{toast.texto}</span>
            {toast.deshacer && (
              <button
                onClick={async () => {
                  const d = toast.deshacer!;
                  setToast(null);
                  await d();
                  refrescar();
                }}
                className="press min-h-9 rounded-xl bg-ground/15 px-3 font-bold"
              >
                Deshacer
              </button>
            )}
          </div>
        </div>
      )}
    </AppCtx.Provider>
  );
}

function TabLink({ href, label, activo, Icon }: { href: string; label: string; activo: boolean; Icon: typeof Home }) {
  return (
    <Link
      href={href}
      aria-current={activo ? "page" : undefined}
      className={cx("press flex min-h-12 flex-col items-center gap-1 text-[11px] font-bold", activo ? "text-accent" : "text-faint")}
    >
      <Icon size={22} strokeWidth={activo ? 2.4 : 2} />
      {label}
    </Link>
  );
}

export { SelectorTema };

export function Salir() {
  const [requiere, setRequiere] = useState(false);
  useEffect(() => {
    fetch("/api/auth/estado").then((r) => r.json()).then((e) => setRequiere(!!e.requiere)).catch(() => {});
  }, []);
  if (!requiere) return null;
  return (
    <button
      onClick={async () => { await fetch("/api/auth/logout", { method: "POST" }); window.location.href = "/entrar"; }}
      className="press flex min-h-10 items-center gap-2 rounded-xl px-3 text-sm font-bold text-muted hover:bg-surface-2"
    >
      <LogOut size={17} /> Salir
    </button>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <SWRConfig value={{ fetcher, revalidateOnFocus: true }}>
      {pathname === "/entrar" ? children : <Interior>{children}</Interior>}
    </SWRConfig>
  );
}
