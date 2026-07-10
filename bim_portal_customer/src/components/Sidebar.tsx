"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home,
  LayoutDashboard,
  User,
  Menu,
  X,
  BookOpen,
  Building2,
  Camera,
  ChevronDown,
  ChevronRight,
  HardHat,
  CalendarOff,
  Receipt,
  FileText,
} from "lucide-react";
import { useState, useEffect } from "react";
import { getStoredPartner, refreshPartner } from "@/lib/auth";

const empleadoItems = [
  { label: "Inicio",    href: "/dashboard/inicio",    icon: Home },
  { label: "Dashboard", href: "/dashboard",           icon: LayoutDashboard },
  { label: "Ausencias", href: "/dashboard/ausencias", icon: CalendarOff },
  { label: "Facturas",  href: "/dashboard/facturas",  icon: Receipt },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [isEmployee, setIsEmployee] = useState(false);
  const [isCustomer, setIsCustomer] = useState(false);
  const [empleadoOpen, setEmpleadoOpen] = useState(false);
  const [clienteOpen, setClienteOpen] = useState(false);

  useEffect(() => {
    const cached = getStoredPartner();
    if (cached) {
      setIsEmployee(cached.is_employee ?? false);
      setIsCustomer(cached.is_customer ?? false);
    }
    refreshPartner().then((fresh) => {
      if (fresh) {
        setIsEmployee(fresh.is_employee ?? false);
        setIsCustomer(fresh.is_customer ?? false);
      }
    });
  }, []);

  // Auto-abrir secciones según ruta activa
  useEffect(() => {
    if (
      pathname === "/dashboard" ||
      pathname === "/dashboard/inicio" ||
      pathname.startsWith("/dashboard/ausencias")
    ) setEmpleadoOpen(true);
    if (pathname.startsWith("/dashboard/cliente")) setClienteOpen(true);
  }, [pathname]);

  const isActive = (href: string) =>
    href === "/dashboard" || href === "/dashboard/inicio"
      ? pathname === href
      : pathname.startsWith(href);

  const linkClass = (href: string) =>
    `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
      isActive(href)
        ? "bg-[#5c2d5c] text-white"
        : "text-white/70 hover:bg-white/10 hover:text-white"
    }`;

  return (
    <aside
      className={`flex flex-col h-full transition-all duration-300 ${
        collapsed ? "w-16" : "w-56"
      } bg-[#3b1a3a] text-white shrink-0`}
    >
      {/* Brand header */}
      <div className="flex items-center justify-between px-4 py-5 border-b border-white/10">
        {!collapsed && (
          <span className="text-lg font-bold tracking-tight text-white">Portal BIM 2.0</span>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1.5 rounded-lg hover:bg-white/10 transition-colors"
          aria-label="Toggle sidebar"
        >
          {collapsed ? <Menu className="w-5 h-5" /> : <X className="w-5 h-5" />}
        </button>
      </div>

      {/* Nav items */}
      <nav className="flex-1 px-2 py-4 space-y-1 overflow-y-auto">

        {/* ── Empleado (expandible) ── */}
        {isEmployee && (
          <div>
            <button
              onClick={() => !collapsed && setEmpleadoOpen((o) => !o)}
              className={`flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                empleadoOpen && !collapsed
                  ? "text-white"
                  : "text-white/70 hover:bg-white/10 hover:text-white"
              }`}
            >
              <HardHat className="shrink-0" size={18} />
              {!collapsed && (
                <>
                  <span className="flex-1 text-left">Empleado</span>
                  {empleadoOpen
                    ? <ChevronDown className="w-4 h-4" />
                    : <ChevronRight className="w-4 h-4" />}
                </>
              )}
            </button>

            {!collapsed && empleadoOpen && (
              <div className="mt-0.5 ml-4 space-y-0.5 border-l border-white/10 pl-3">
                {empleadoItems.map(({ label, href, icon: Icon }) => (
                  <Link
                    key={href}
                    href={href}
                    className={`flex items-center gap-2 px-2 py-2 rounded-lg text-sm transition-colors ${
                      isActive(href)
                        ? "bg-[#5c2d5c] text-white"
                        : "text-white/60 hover:bg-white/10 hover:text-white"
                    }`}
                  >
                    <Icon size={15} className="shrink-0" />
                    <span>{label}</span>
                  </Link>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── Tecno Cartas (nivel superior) ── */}
        <Link href="/dashboard/tecno-cartas" className={linkClass("/dashboard/tecno-cartas")}>
          <BookOpen className="shrink-0" size={18} />
          {!collapsed && <span>Tecno Cartas</span>}
        </Link>

        {/* ── Cliente (expandible) ── */}
        {isCustomer && (
          <div>
            <button
              onClick={() => !collapsed && setClienteOpen((o) => !o)}
              className={`flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                pathname.startsWith("/dashboard/cliente")
                  ? "bg-[#5c2d5c] text-white"
                  : "text-white/70 hover:bg-white/10 hover:text-white"
              }`}
            >
              <Building2 className="shrink-0" size={18} />
              {!collapsed && (
                <>
                  <span className="flex-1 text-left">Cliente</span>
                  {clienteOpen
                    ? <ChevronDown className="w-4 h-4" />
                    : <ChevronRight className="w-4 h-4" />}
                </>
              )}
            </button>

            {!collapsed && clienteOpen && (
              <div className="mt-0.5 ml-4 space-y-0.5 border-l border-white/10 pl-3">
                <Link
                  href="/dashboard/cliente/avances"
                  className={`flex items-center gap-2 px-2 py-2 rounded-lg text-sm transition-colors ${
                    pathname.startsWith("/dashboard/cliente/avances")
                      ? "bg-[#5c2d5c] text-white"
                      : "text-white/60 hover:bg-white/10 hover:text-white"
                  }`}
                >
                  <Camera size={15} className="shrink-0" />
                  <span>Avances de Obra</span>
                </Link>
                <Link
                  href="/dashboard/cliente/documentos"
                  className={`flex items-center gap-2 px-2 py-2 rounded-lg text-sm transition-colors ${
                    pathname.startsWith("/dashboard/cliente/documentos")
                      ? "bg-[#5c2d5c] text-white"
                      : "text-white/60 hover:bg-white/10 hover:text-white"
                  }`}
                >
                  <FileText size={15} className="shrink-0" />
                  <span>Documentos</span>
                </Link>
              </div>
            )}
          </div>
        )}

        {/* ── Perfil ── */}
        <Link href="/dashboard/perfil" className={linkClass("/dashboard/perfil")}>
          <User className="shrink-0" size={18} />
          {!collapsed && <span>Perfil</span>}
        </Link>
      </nav>

      {/* Bottom: version */}
      {!collapsed && (
        <div className="px-4 py-3 border-t border-white/10">
          <p className="text-white/30 text-xs">BIM Portal v1.0</p>
        </div>
      )}
    </aside>
  );
}
