import {
  Banknote, Briefcase, HandCoins, UserRound, Bus, Car, CircleDashed, Coffee, Fuel, Gift, GraduationCap, HeartPulse, House,
  Landmark, Laptop, Percent, PiggyBank, Repeat, Shirt, ShoppingCart, Smartphone, Sofa, Tag, Ticket,
  UtensilsCrossed, Wallet, type LucideIcon,
} from "lucide-react";

export const ICONOS: Record<string, LucideIcon> = {
  carrito: ShoppingCart,
  comida: UtensilsCrossed,
  cafe: Coffee,
  auto: Fuel,
  vehiculo: Car,
  transporte: Bus,
  casa: House,
  salud: HeartPulse,
  suscripcion: Repeat,
  ropa: Shirt,
  hogar: Sofa,
  salidas: Ticket,
  regalo: Gift,
  educacion: GraduationCap,
  comision: Percent,
  otros: CircleDashed,
  sueldo: Briefcase,
  trabajo: Laptop,
  venta: Tag,
  ingreso: PiggyBank,
  deuda: HandCoins,
  persona: UserRound,
  prestamo: Landmark,
  // cuentas
  banco: Landmark,
  billetera: Smartphone,
  efectivo: Banknote,
  tarjeta_credito: Wallet,
};

export const COLORES = ["green", "orange", "red", "amber", "blue", "pink", "purple", "indigo", "teal", "slate"] as const;
