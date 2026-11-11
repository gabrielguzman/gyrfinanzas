"use client";

import { useRef } from "react";
import { Paperclip } from "lucide-react";
import { Boton } from "./ui";

/** Abre la cámara en el celu (o el selector de archivos en la compu). */
export function AdjuntarBoton({
  onArchivo,
  texto = "Adjuntar comprobante",
  className,
  soloIcono,
}: {
  onArchivo: (f: File) => void;
  texto?: string;
  className?: string;
  soloIcono?: boolean;
}) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <>
      <input
        ref={ref}
        type="file"
        accept="image/*,application/pdf"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onArchivo(f);
          e.target.value = "";
        }}
      />
      <Boton
        type="button"
        variante="fantasma"
        className={className}
        onClick={() => ref.current?.click()}
        aria-label={soloIcono ? texto : undefined}
        title={soloIcono ? texto : undefined}
      >
        <Paperclip size={17} />
        {!soloIcono && texto}
      </Boton>
    </>
  );
}
