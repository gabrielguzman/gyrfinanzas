"use client";

import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { Plus } from "lucide-react";
import { MetaCard, MetaSheet, type MetaAbierta } from "@/components/Metas";
import { Boton, Esqueleto, Seccion, Titulo, Vacio } from "@/components/ui";
import type { Meta } from "@/lib/api";
import { monto } from "@/lib/format";

export default function MetasPage() {
  const { data } = useSWR<Meta[]>("/metas");
  const [abierta, setAbierta] = useState<MetaAbierta>(null);
  const activas = (data ?? []).filter((m) => !m.cumplida);
  const cumplidas = (data ?? []).filter((m) => m.cumplida);
  const porMes = activas.reduce((s, m) => s + Number(m.por_mes_ars ?? 0), 0);

  return (
    <div className="flex flex-col gap-7">
      <Titulo extra={<Boton variante="acento" onClick={() => setAbierta({ nueva: true })}><Plus size={18} /> Nueva</Boton>}>Metas</Titulo>
      {!data ? (
        <Esqueleto className="h-60 rounded-[22px]" />
      ) : !data.length ? (
        <Vacio titulo="Ponele nombre a lo que querés juntar" accion={<Boton variante="acento" onClick={() => setAbierta({ nueva: true })}><Plus size={18} /> Crear la primera</Boton>}>
          Unas vacaciones, un fondo de emergencia en dólares, el auto. Te digo cuánto apartar por mes, lo descuento de lo que podés gastar y te aviso si te atrasás.
        </Vacio>
      ) : (
        <div className="grid grid-cols-1 gap-7 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] lg:items-start lg:gap-10">
          <div className="flex min-w-0 flex-col gap-3">
            {activas.map((m) => <MetaCard key={m.id} m={m} onAbrir={() => setAbierta({ id: m.id })} />)}
            {cumplidas.length > 0 && (
              <Seccion titulo="Cumplidas">
                {cumplidas.map((m) => <MetaCard key={m.id} m={m} onAbrir={() => setAbierta({ id: m.id })} />)}
              </Seccion>
            )}
          </div>
          {porMes > 0 && (
            <section className="flex flex-col gap-3 rounded-[28px] bg-slab p-6 text-slab-ink shadow-soft lg:sticky lg:top-10">
              <p className="text-sm text-slab-muted">Tus metas piden</p>
              <p className="display num text-[44px] leading-none font-bold">{monto(Math.round(porMes))}</p>
              <p className="text-sm text-slab-muted">por mes. Ya lo aparto de lo que podés gastar cada día.</p>
              <Link href="/plan" className="press mt-1 w-fit rounded-2xl bg-white/10 px-4 py-2.5 text-sm font-bold">Ver hasta el cobro</Link>
            </section>
          )}
        </div>
      )}
      <MetaSheet abierta={abierta} onCerrar={() => setAbierta(null)} />
    </div>
  );
}
