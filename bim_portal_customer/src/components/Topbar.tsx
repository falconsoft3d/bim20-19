"use client";

import { useRouter } from "next/navigation";
import { LogOut, Bell } from "lucide-react";
import { logout, getStoredPartner } from "@/lib/auth";
import { useEffect, useState } from "react";

export default function Topbar() {
  const router = useRouter();
  const [userName, setUserName] = useState("...");

  useEffect(() => {
    const partner = getStoredPartner();
    if (partner?.name) setUserName(partner.name.toUpperCase());
  }, []);

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  return (
    <header className="h-14 bg-[#3b1a3a] flex items-center justify-between px-6 shrink-0">
      <div />
      <div className="flex items-center gap-4">
        <button className="p-1.5 rounded-lg text-white/70 hover:text-white hover:bg-white/10 transition-colors">
          <Bell className="w-4.5 h-4.5" size={18} />
        </button>
        <span className="text-white text-sm font-medium hidden sm:block">{userName}</span>
        <button
          onClick={handleLogout}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white text-sm font-medium transition-colors"
        >
          <LogOut className="w-4 h-4" />
          <span className="hidden sm:inline">Cerrar sesión</span>
        </button>
      </div>
    </header>
  );
}
