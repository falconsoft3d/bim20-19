"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { User, Mail, Phone, Building2, Lock, Eye, EyeOff, Save, Pencil, X } from "lucide-react";
import { fetchProfile, updateProfile, changePassword } from "@/lib/profile";
import { PartnerProfile } from "@/lib/auth";

// ── Sub-componente: campo editable ────────────────────────────────────────────

function InfoRow({
  icon: Icon,
  label,
  value,
  editing,
  name,
  type = "text",
  onChange,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  editing: boolean;
  name: string;
  type?: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <div className="flex items-start gap-3 py-3 border-b border-gray-100 last:border-0">
      <div className="w-8 h-8 rounded-lg bg-[#3b1a3a]/10 flex items-center justify-center shrink-0 mt-0.5">
        <Icon className="w-4 h-4 text-[#3b1a3a]" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-gray-500 mb-0.5">{label}</p>
        {editing ? (
          <input
            type={type}
            name={name}
            value={value}
            onChange={onChange}
            className="w-full text-sm text-gray-800 border border-gray-300 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-[#5c2d5c]"
          />
        ) : (
          <p className="text-sm font-medium text-gray-800 truncate">{value || "—"}</p>
        )}
      </div>
    </div>
  );
}

// ── Notificación inline ───────────────────────────────────────────────────────

function Alert({
  type,
  message,
  onClose,
}: {
  type: "success" | "error";
  message: string;
  onClose: () => void;
}) {
  const base =
    type === "success"
      ? "bg-green-50 border-green-200 text-green-700"
      : "bg-red-50 border-red-200 text-red-600";
  return (
    <div className={`flex items-center justify-between border rounded-lg px-4 py-3 text-sm ${base}`}>
      <span>{message}</span>
      <button onClick={onClose} className="ml-3 opacity-60 hover:opacity-100">
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

// ── Página principal ──────────────────────────────────────────────────────────

export default function PerfilPage() {
  const router = useRouter();
  const [partner, setPartner] = useState<PartnerProfile | null>(null);
  const [loading, setLoading] = useState(true);

  // Estado formulario datos
  const [editingData, setEditingData] = useState(false);
  const [formData, setFormData] = useState({ name: "", email: "", phone: "" });
  const [savingData, setSavingData] = useState(false);
  const [dataAlert, setDataAlert] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  // Estado formulario contraseña
  const [pwForm, setPwForm] = useState({ current_password: "", new_password: "", confirm_password: "" });
  const [showPw, setShowPw] = useState({ current: false, newPw: false, confirm: false });
  const [savingPw, setSavingPw] = useState(false);
  const [pwAlert, setPwAlert] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("bim_portal_token");
    if (!token) { router.push("/login"); return; }

    fetchProfile().then((p) => {
      if (!p) { router.push("/login"); return; }
      setPartner(p);
      setFormData({ name: p.name, email: p.email, phone: p.phone });
      setLoading(false);
    });
  }, [router]);

  // ── Handlers datos ──────────────────────────────────────────────────────

  function handleDataChange(e: React.ChangeEvent<HTMLInputElement>) {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  }

  async function handleSaveData() {
    setSavingData(true);
    setDataAlert(null);
    try {
      const res = await updateProfile(formData);
      if (res.success && res.partner) {
        setPartner(res.partner);
        setFormData({ name: res.partner.name, email: res.partner.email, phone: res.partner.phone });
        setEditingData(false);
        setDataAlert({ type: "success", msg: "Datos actualizados correctamente." });
      } else {
        setDataAlert({ type: "error", msg: res.error || "Error al guardar." });
      }
    } catch {
      setDataAlert({ type: "error", msg: "No se pudo conectar con el servidor." });
    } finally {
      setSavingData(false);
    }
  }

  function handleCancelData() {
    if (partner) setFormData({ name: partner.name, email: partner.email, phone: partner.phone });
    setEditingData(false);
    setDataAlert(null);
  }

  // ── Handlers contraseña ─────────────────────────────────────────────────

  function handlePwChange(e: React.ChangeEvent<HTMLInputElement>) {
    setPwForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  }

  async function handleSavePw(e: React.FormEvent) {
    e.preventDefault();
    setPwAlert(null);
    if (pwForm.new_password !== pwForm.confirm_password) {
      setPwAlert({ type: "error", msg: "Las contraseñas nuevas no coinciden." });
      return;
    }
    if (pwForm.new_password.length < 8) {
      setPwAlert({ type: "error", msg: "La contraseña debe tener al menos 8 caracteres." });
      return;
    }
    setSavingPw(true);
    try {
      const res = await changePassword(pwForm);
      if (res.success) {
        setPwAlert({ type: "success", msg: "Contraseña cambiada correctamente." });
        setPwForm({ current_password: "", new_password: "", confirm_password: "" });
      } else {
        setPwAlert({ type: "error", msg: res.error || "Error al cambiar la contraseña." });
      }
    } catch {
      setPwAlert({ type: "error", msg: "No se pudo conectar con el servidor." });
    } finally {
      setSavingPw(false);
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-[#3b1a3a] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-800">Mi Perfil</h1>
        <p className="text-sm text-gray-500 mt-0.5">Gestiona tus datos personales y contraseña</p>
      </div>

      {/* ── Datos personales ───────────────────────────────────────────── */}
      <div className="bg-white rounded-xl shadow-sm">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wide">Datos personales</h2>
          {!editingData ? (
            <button
              onClick={() => setEditingData(true)}
              className="flex items-center gap-1.5 text-sm text-[#3b1a3a] hover:text-[#5c2d5c] font-medium"
            >
              <Pencil className="w-3.5 h-3.5" />
              Editar
            </button>
          ) : (
            <div className="flex gap-2">
              <button
                onClick={handleCancelData}
                className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
              >
                <X className="w-3.5 h-3.5" />
                Cancelar
              </button>
              <button
                onClick={handleSaveData}
                disabled={savingData}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#3b1a3a] hover:bg-[#5c2d5c] text-white text-sm font-medium transition-colors disabled:opacity-60"
              >
                <Save className="w-3.5 h-3.5" />
                {savingData ? "Guardando..." : "Guardar"}
              </button>
            </div>
          )}
        </div>

        <div className="px-5 py-2">
          {dataAlert && (
            <div className="mb-3 mt-2">
              <Alert type={dataAlert.type} message={dataAlert.msg} onClose={() => setDataAlert(null)} />
            </div>
          )}
          <InfoRow icon={User}     label="Nombre completo" name="name"  value={formData.name}  editing={editingData} onChange={handleDataChange} />
          <InfoRow icon={Mail}     label="Email"           name="email" value={formData.email} editing={editingData} onChange={handleDataChange} type="email" />
          <InfoRow icon={Phone}    label="Teléfono"        name="phone" value={formData.phone} editing={editingData} onChange={handleDataChange} type="tel" />
          <InfoRow icon={Building2} label="Empresa"        name="company" value={partner?.company || ""} editing={false} onChange={() => {}} />
        </div>

        {/* Avatar / login badge */}
        <div className="px-5 py-4 border-t border-gray-100 flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-[#3b1a3a] flex items-center justify-center text-white font-bold text-sm shrink-0">
            {partner?.name?.charAt(0).toUpperCase()}
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-800">{partner?.name}</p>
            <p className="text-xs text-gray-500">@{partner?.login}</p>
          </div>
          <div className="ml-auto flex flex-wrap gap-1.5">
            {partner?.is_customer    && <span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 text-xs font-medium">Cliente</span>}
            {partner?.is_employee    && <span className="px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 text-xs font-medium">Empleado</span>}
            {partner?.is_admin       && <span className="px-2 py-0.5 rounded-full bg-orange-100 text-orange-700 text-xs font-medium">Admin</span>}
            {partner?.is_tecno_cartas && <span className="px-2 py-0.5 rounded-full bg-teal-100 text-teal-700 text-xs font-medium">Tecno Cartas</span>}
            {partner?.is_proveedor   && <span className="px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-700 text-xs font-medium">Proveedor</span>}
          </div>
        </div>
      </div>

      {/* ── Cambiar contraseña ─────────────────────────────────────────── */}
      <div className="bg-white rounded-xl shadow-sm">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wide flex items-center gap-2">
            <Lock className="w-4 h-4" />
            Cambiar contraseña
          </h2>
        </div>

        <form onSubmit={handleSavePw} className="px-5 py-4 space-y-4">
          {pwAlert && (
            <Alert type={pwAlert.type} message={pwAlert.msg} onClose={() => setPwAlert(null)} />
          )}

          {/* Contraseña actual */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">Contraseña actual</label>
            <div className="relative">
              <input
                type={showPw.current ? "text" : "password"}
                name="current_password"
                value={pwForm.current_password}
                onChange={handlePwChange}
                autoComplete="current-password"
                className="w-full pr-10 px-3 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#5c2d5c]"
                placeholder="••••••••"
              />
              <button type="button" onClick={() => setShowPw((p) => ({ ...p, current: !p.current }))}
                className="absolute right-3 top-2.5 text-gray-400 hover:text-gray-600">
                {showPw.current ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Nueva contraseña */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">Nueva contraseña</label>
            <div className="relative">
              <input
                type={showPw.newPw ? "text" : "password"}
                name="new_password"
                value={pwForm.new_password}
                onChange={handlePwChange}
                autoComplete="new-password"
                className="w-full pr-10 px-3 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#5c2d5c]"
                placeholder="Mínimo 8 caracteres"
              />
              <button type="button" onClick={() => setShowPw((p) => ({ ...p, newPw: !p.newPw }))}
                className="absolute right-3 top-2.5 text-gray-400 hover:text-gray-600">
                {showPw.newPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {/* Barra de fortaleza */}
            {pwForm.new_password && (
              <PasswordStrengthBar password={pwForm.new_password} />
            )}
          </div>

          {/* Confirmar contraseña */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">Confirmar nueva contraseña</label>
            <div className="relative">
              <input
                type={showPw.confirm ? "text" : "password"}
                name="confirm_password"
                value={pwForm.confirm_password}
                onChange={handlePwChange}
                autoComplete="new-password"
                className="w-full pr-10 px-3 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#5c2d5c]"
                placeholder="Repite la nueva contraseña"
              />
              <button type="button" onClick={() => setShowPw((p) => ({ ...p, confirm: !p.confirm }))}
                className="absolute right-3 top-2.5 text-gray-400 hover:text-gray-600">
                {showPw.confirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={savingPw}
            className="w-full py-2.5 rounded-lg bg-[#3b1a3a] hover:bg-[#5c2d5c] text-white text-sm font-semibold transition-colors disabled:opacity-60"
          >
            {savingPw ? "Actualizando..." : "Cambiar contraseña"}
          </button>
        </form>
      </div>
    </div>
  );
}

// ── Barra de fortaleza de contraseña ─────────────────────────────────────────

function PasswordStrengthBar({ password }: { password: string }) {
  let score = 0;
  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/[a-z]/.test(password)) score++;
  if (/\d/.test(password)) score++;
  if (/[!@#$%^&*()\-_=+]/.test(password)) score++;

  const level = score <= 2 ? "débil" : score <= 4 ? "media" : "fuerte";
  const bars = score <= 2 ? 1 : score <= 4 ? 2 : 3;
  const colors = ["bg-red-400", "bg-yellow-400", "bg-green-500"];

  return (
    <div className="mt-1.5 flex items-center gap-2">
      <div className="flex gap-1 flex-1">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className={`h-1.5 flex-1 rounded-full transition-all ${
              i < bars ? colors[bars - 1] : "bg-gray-200"
            }`}
          />
        ))}
      </div>
      <span className="text-xs text-gray-500 capitalize w-10">{level}</span>
    </div>
  );
}
