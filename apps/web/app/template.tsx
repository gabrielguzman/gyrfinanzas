// Se vuelve a montar en cada cambio de pantalla: una sola entrada suave.
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="anim-pantalla">{children}</div>;
}
