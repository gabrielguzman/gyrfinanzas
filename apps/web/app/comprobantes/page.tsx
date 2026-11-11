"use client";

import { useState } from "react";
import useSWR from "swr";
import { FileText } from "lucide-react";
import { AdjuntarBoton } from "@/components/AdjuntarBoton";
import { useApp } from "@/components/Shell";
import { Chip, Esqueleto, Titulo, Vacio } from "@/components/ui";
import { api, ApiError, type Archivo } from "@/lib/api";

const peso = (n: number) => (n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.ceil(n / 1024)} KB`);

export default function ComprobantesPage() {
  const { aviso, refrescar } = useApp();
  const [soloSueltos, setSoloSueltos] = useState(false);
  const { data } = useSWR<Archivo[]>(`/archivos${soloSueltos ? "?sin_vincular=true" : ""}`);

  return (
    <div className="flex flex-col gap-5">
      <Titulo>Comprobantes</Titulo>
      <div className="flex flex-wrap items-center gap-2">
        <Chip activo={!soloSueltos} onClick={() => setSoloSueltos(false)}>Todos</Chip>
        <Chip activo={soloSueltos} onClick={() => setSoloSueltos(true)}>Sin vincular</Chip>
        <div className="ml-auto">
          <AdjuntarBoton
            texto="Subir"
            onArchivo={async (f) => {
              try {
                await api.subir("/archivos", f);
                aviso("Guardado. Podés vincularlo a un gasto desde su detalle.");
                refrescar();
              } catch (e) {
                aviso(e instanceof ApiError ? e.message : "No pude conectar con el servidor");
              }
            }}
          />
        </div>
      </div>

      {!data && <Esqueleto className="h-64 rounded-[22px]" />}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {data?.map((a) => (
          <a
            key={a.id}
            href={api.urlArchivo(a.id)}
            target="_blank"
            rel="noreferrer"
            className="press group flex flex-col overflow-hidden rounded-[20px] bg-surface shadow-soft"
          >
            <div className="flex aspect-[4/5] items-center justify-center overflow-hidden bg-surface-2">
              {a.mime.startsWith("image/") ? (
                <img src={api.urlArchivo(a.id)} alt="" loading="lazy" className="h-full w-full object-cover transition-transform group-hover:scale-[1.03]" />
              ) : (
                <FileText size={36} className="text-faint" />
              )}
            </div>
            <div className="flex flex-col gap-0.5 p-3">
              <span className="truncate text-[13px] font-bold">{a.nombre_original}</span>
              <span className="text-xs text-muted">
                {a.movimientos.length ? `En ${a.movimientos.length} ${a.movimientos.length === 1 ? "movimiento" : "movimientos"}` : a.garantia ? `Garantía: ${a.garantia}` : "Sin vincular"}
                {" · "}{peso(a.tamano)}
              </span>
            </div>
          </a>
        ))}
      </div>
      {data?.length === 0 && (
        <Vacio titulo={soloSueltos ? "No hay comprobantes sueltos" : "Todavía no hay comprobantes"}>
          Sacale foto al próximo ticket desde la carga, o mandásela al bot de Telegram.
        </Vacio>
      )}
    </div>
  );
}
