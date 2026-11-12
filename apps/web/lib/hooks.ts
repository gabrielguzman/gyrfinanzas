"use client";

import { useEffect, useRef, useState } from "react";

/** Anima un número desde el valor anterior hasta el nuevo. */
export function useContador(objetivo: number, ms = 700): number {
  const [valor, setValor] = useState(objetivo);
  const desde = useRef(objetivo);
  const primero = useRef(true);
  useEffect(() => {
    const reducido = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const inicio = primero.current ? 0 : desde.current;
    primero.current = false;
    if (reducido || inicio === objetivo) {
      setValor(objetivo);
      desde.current = objetivo;
      return;
    }
    let raf = 0;
    const t0 = performance.now();
    const paso = (t: number) => {
      const p = Math.min(1, (t - t0) / ms);
      const e = 1 - Math.pow(1 - p, 3);
      const v = inicio + (objetivo - inicio) * e;
      setValor(v);
      desde.current = v;
      if (p < 1) raf = requestAnimationFrame(paso);
    };
    raf = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(raf);
  }, [objetivo, ms]);
  return valor;
}

export type Tema = "system" | "light" | "dark";

export function useTema(): [Tema, (t: Tema) => void] {
  const [tema, setTemaState] = useState<Tema>("system");
  useEffect(() => {
    try {
      const t = localStorage.getItem("gyr-tema");
      if (t === "light" || t === "dark") setTemaState(t);
    } catch {
      /* sin almacenamiento */
    }
  }, []);
  const setTema = (t: Tema) => {
    setTemaState(t);
    try {
      if (t === "system") localStorage.removeItem("gyr-tema");
      else localStorage.setItem("gyr-tema", t);
    } catch {
      /* sin almacenamiento */
    }
    if (t === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = t;
  };
  return [tema, setTema];
}

/** Modo discreto: oculta los montos (borrosos) en este dispositivo. */
export function useDiscreto(): [boolean, () => void] {
  const [on, setOn] = useState(false);
  useEffect(() => {
    const leer = () => setOn(document.documentElement.classList.contains("discreto"));
    leer();
    window.addEventListener("gyr-discreto", leer);
    return () => window.removeEventListener("gyr-discreto", leer);
  }, []);
  const alternar = () => {
    const nuevo = !document.documentElement.classList.contains("discreto");
    document.documentElement.classList.toggle("discreto", nuevo);
    try {
      if (nuevo) localStorage.setItem("gyr-discreto", "1");
      else localStorage.removeItem("gyr-discreto");
    } catch {
      /* sin almacenamiento */
    }
    window.dispatchEvent(new Event("gyr-discreto"));
  };
  return [on, alternar];
}

export function vibrar(ms = 12) {
  try {
    navigator.vibrate?.(ms);
  } catch {
    /* no soportado */
  }
}
