import { api, type SugerenciaRegla } from "./api";

type Aviso = (texto: string, o?: { accion?: { texto: string; fn: () => unknown } }) => void;

/** Después de cambiarle la categoría a algo: «¿Todo lo que diga uber va a Transporte?». */
export async function ofrecerRegla(movId: string, categoriaId: string, categoria: string, aviso: Aviso) {
  try {
    const s = await api.get<SugerenciaRegla>(`/reglas/sugerencia/${movId}`);
    if (!s.texto || s.existe) return;
    const mas = s.a_cambiar > 0 ? ` (y cambio ${s.a_cambiar === 1 ? "1 que ya cargaste" : `${s.a_cambiar} que ya cargaste`})` : "";
    aviso(`¿Todo lo que diga «${s.texto}» va a ${categoria}?${mas}`, {
      accion: {
        texto: "Sí, siempre",
        fn: async () => {
          const r = await api.post<{ cambiados: number }>("/reglas", { texto: s.texto, categoria_id: categoriaId, aplicar: true });
          aviso(r.cambiados ? `Listo: regla creada y ${r.cambiados} recategorizados` : "Listo: regla creada");
        },
      },
    });
  } catch {
    /* sin sugerencia */
  }
}
