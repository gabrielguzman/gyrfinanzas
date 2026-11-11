"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import useSWR from "swr";
import { CalendarClock, ThumbsDown, ThumbsUp } from "lucide-react";
import { CategoriasBarras } from "@/components/Graficos";
import { HallazgoFila } from "@/components/Hallazgos";
import { Esqueleto, IconoCat, Lista, Seccion, Titulo, Vacio, cx } from "@/components/ui";
import { api, type Hallazgo, type Movimiento, type Semana } from "@/lib/api";
import { etiquetaDia, fechaCorta, monto } from "@/lib/format";
import { useContador, vibrar } from "@/lib/hooks";

function Repaso({ inicial }: { inicial: Movimiento[] }) {
  const [respuestas, setRespuestas] = useState<Record<string, boolean>>({});
  const pendientes = inicial.filter((m) => !(m.id in respuestas));
  const actual = pendientes[0];
  const hechos = inicial.length - pendientes.length;

  async function responder(m: Movimiento, valio: boolean) {
    vibrar();
    setRespuestas((r) => ({ ...r, [m.id]: valio }));
    await api.post(`/movimientos/${m.id}/valio`, { valio }).catch(() => {});
  }

  if (!inicial.length) return null;
  return (
    <Seccion titulo="¿Valió la pena?" extra={<span className="text-[13px] font-semibold text-muted">{hechos} de {inicial.length}</span>}>
      <p className="-mt-1 text-sm text-muted">Cinco gastos de la semana. Sin culpa: es para ver dónde se te va la plata en cosas que después no valoraste.</p>
      {actual ? (
        <div key={actual.id} className="anim-pantalla flex flex-col items-center gap-4 rounded-[24px] bg-surface p-6 text-center shadow-soft">
          <IconoCat icono={actual.categoria_icono} color={actual.categoria_color} size={56} />
          <div>
            <p className="text-xl font-extrabold">{actual.descripcion}</p>
            <p className="text-sm text-muted">{etiquetaDia(actual.fecha)} · {actual.categoria ?? "Sin categoría"}</p>
          </div>
          <p className="display num text-[40px] leading-none font-bold">{monto(actual.monto)}</p>
          <div className="grid w-full grid-cols-2 gap-2.5">
            <button onClick={() => responder(actual, false)} className="press flex min-h-14 items-center justify-center gap-2 rounded-2xl border border-line-strong bg-surface text-base font-bold">
              <ThumbsDown size={20} /> No
            </button>
            <button onClick={() => responder(actual, true)} className="press flex min-h-14 items-center justify-center gap-2 rounded-2xl bg-ink text-base font-bold text-ground">
              <ThumbsUp size={20} /> Sí
            </button>
          </div>
        </div>
      ) : (
        <div className="anim-pantalla rounded-[22px] bg-ok-soft p-5">
          <p className="font-bold">¡Listo por esta semana!</p>
          <p className="text-sm text-muted">
            Dijiste que no a {Object.values(respuestas).filter((v) => !v).length} de {inicial.length}. Con algunas semanas más te muestro en qué categorías te arrepentís más.
          </p>
        </div>
      )}
      <div className="flex gap-1" aria-hidden>
        {inicial.map((m, i) => (
          <span
            key={m.id}
            className="h-1.5 flex-1 rounded-full"
            style={{ background: m.id in respuestas ? (respuestas[m.id] ? "var(--ok)" : "var(--warn)") : i === hechos ? "var(--line-strong)" : "var(--line)" }}
          />
        ))}
      </div>
    </Seccion>
  );
}

export default function SemanaPage() {
  const { data: s } = useSWR<Semana>("/semana");
  const { data: todos } = useSWR<Hallazgo[]>("/hallazgos");
  const total = Number(s?.gastos ?? 0);
  const animado = useContador(total);
  const repaso = useMemo(() => s?.repaso ?? [], [s?.desde]); // fijo mientras respondés

  if (!s) return <Esqueleto className="h-96 rounded-[28px]" />;
  // Se compara sin los fijos: el alquiler no dice nada de cómo gastaste la semana.
  const fijos = Number(s.fijos);
  const vars = Number(s.variables);
  const antes = Number(s.variables_anterior);
  const dif = vars - antes;
  const pct = antes > 0 ? Math.round((Math.abs(dif) / antes) * 100) : null;
  const peores = s.arrepentimientos.filter((a) => a.no / a.respondidos >= 0.5);

  return (
    <div className="flex flex-col gap-7">
      <Titulo>Tu semana</Titulo>
      <div className="grid grid-cols-1 gap-7 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] lg:items-start lg:gap-10">
        <div className="flex min-w-0 flex-col gap-7">
          <section className="flex flex-col gap-5 rounded-[28px] bg-slab p-6 text-slab-ink shadow-soft lg:p-8">
            <p className="text-sm text-slab-muted">Del lunes {fechaCorta(s.desde)} al domingo {fechaCorta(s.hasta)}</p>
            <div>
              <p className="text-sm text-slab-muted">Gastaste</p>
              <p className="display num text-[clamp(40px,11vw,56px)] leading-[0.95] font-bold">{monto(Math.round(animado))}</p>
              <p className="mt-2 text-sm text-slab-muted">
                {s.cantidad} gastos{fijos > 0 && `, de los cuales ${monto(fijos)} fueron fijos`}.
              </p>
            </div>
            {pct != null && (
              <p className="text-[15px] font-semibold">
                {fijos > 0 ? `Sin contar fijos: ${monto(vars)}, ` : ""}
                {pct < 3 ? "casi igual que la semana anterior." : `${pct}% ${dif < 0 ? "menos" : "más"} que la semana anterior (${monto(antes)}).`}
              </p>
            )}
            {s.mayor && (
              <p className="rounded-2xl bg-white/8 p-3 text-sm">
                El más grande: <b>{s.mayor.descripcion}</b>, {monto(s.mayor.monto)} el {fechaCorta(s.mayor.fecha)}.
              </p>
            )}
          </section>

          {s.top.length > 0 && (
            <Seccion titulo="En qué se fue">
              <div className="rounded-[22px] bg-surface p-5 shadow-soft">
                <CategoriasBarras
                  items={s.top.map((t) => ({ categoria_id: null, nombre: t.nombre, icono: t.icono, color: t.color, total: t.total, cantidad: 0 }))}
                  total={total}
                />
              </div>
            </Seccion>
          )}

          <Repaso inicial={repaso} />

          {peores.length > 0 && (
            <Seccion titulo="Donde más te arrepentís">
              <Lista>
                {peores.map((a) => (
                  <div key={a.categoria} className="flex items-center justify-between gap-3 px-4 py-3.5 text-sm">
                    <span className="font-bold">{a.categoria}</span>
                    <span className="text-muted">dijiste que no {a.no} de {a.respondidos} veces</span>
                  </div>
                ))}
              </Lista>
            </Seccion>
          )}
        </div>

        <div className="flex min-w-0 flex-col gap-7">
          {s.vencimientos.length > 0 && (
            <Seccion titulo="Vence esta semana">
              <Lista>
                {s.vencimientos.map((v) => (
                  <div key={v.que + v.fecha} className="flex items-center gap-3 px-4 py-3.5">
                    <CalendarClock size={20} className="shrink-0 text-warn" />
                    <span className="flex-1 text-sm"><b>{fechaCorta(v.fecha)}</b> · {v.que}</span>
                    <span className="num font-extrabold">{monto(v.monto)}</span>
                  </div>
                ))}
              </Lista>
            </Seccion>
          )}

          <Seccion titulo="Para mirar">
            {todos === undefined ? (
              <Esqueleto className="h-40 rounded-[22px]" />
            ) : todos.length ? (
              <Lista>{todos.map((h) => <HallazgoFila key={h.clave} h={h} />)}</Lista>
            ) : (
              <Vacio titulo="Nada raro por ahora">Cuando aparezcan suscripciones que suben, gastos repetidos o comisiones, te aviso acá.</Vacio>
            )}
          </Seccion>

          {s.pendientes > 0 && (
            <Link href="/" className={cx("press rounded-[20px] bg-accent-soft p-4 text-sm font-semibold")}>
              Tenés {s.pendientes} {s.pendientes === 1 ? "cosa" : "cosas"} en la bandeja para confirmar.
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
