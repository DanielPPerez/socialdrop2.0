"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import {
  Save,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Info,
  Key,
  Globe,
  Lock,
} from "lucide-react"

const PLATFORM_CONFIG = [
  { id: "youtube", name: "YouTube", icon: "📺", fields: ["CLIENT_ID", "CLIENT_SECRET"] },
  { id: "tiktok", name: "TikTok", icon: "🎵", fields: ["CLIENT_ID", "CLIENT_SECRET"] },
  { id: "instagram", name: "Instagram", icon: "📷", fields: ["CLIENT_ID", "CLIENT_SECRET"] },
  { id: "x", name: "X (Twitter)", icon: "𝕏", fields: ["CLIENT_ID", "CLIENT_SECRET"] },
  { id: "linkedin", name: "LinkedIn", icon: "💼", fields: ["CLIENT_ID", "CLIENT_SECRET"] },
  { id: "bluesky", name: "Bluesky", icon: "🦋", fields: ["HANDLE", "APP_PASSWORD"] },
] as const

type PlatformId = typeof PLATFORM_CONFIG[number]["id"]
type PlatformFields = Record<PlatformId, Record<string, string>>

export function SettingsClient({ initialMode }: { initialMode: "local" | "cloud" }) {
  const router = useRouter()
  const [mode, setMode] = useState<"local" | "cloud">(initialMode)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null)
  const [formData, setFormData] = useState<PlatformFields>({} as PlatformFields)

  // Load existing env vars on mount
  useEffect(() => {
    if (mode !== "local") {
      router.push("/drops")
      return
    }
    loadEnvVars()
  }, [mode, router])

  const loadEnvVars = async () => {
    try {
      const res = await fetch("/api/local/env", { cache: "no-store" })
      if (res.ok) {
        const data = await res.json()
        const loaded: PlatformFields = {} as PlatformFields
        PLATFORM_CONFIG.forEach((p) => {
          loaded[p.id] = {}
          p.fields.forEach((field) => {
            const envKey = `SOCIALDROP_${p.id.toUpperCase()}_${field}`
            if (data[envKey]) {
              loaded[p.id][field] = data[envKey]
            }
          })
        })
        setFormData(loaded)
      }
    } catch {
      // Ignore errors
    }
  }

  const handleChange = (platform: PlatformId, field: string, value: string) => {
    setFormData((prev) => ({
      ...prev,
      [platform]: { ...prev[platform], [field]: value },
    }))
  }

  const handleSave = async () => {
    if (mode !== "local") return
    setSaving(true)
    setMessage(null)

    // Flatten form data to env vars
    const vars: Record<string, string> = {}
    PLATFORM_CONFIG.forEach((p) => {
      p.fields.forEach((field) => {
        const envKey = `SOCIALDROP_${p.id.toUpperCase()}_${field}`
        const value = formData[p.id]?.[field]
        if (value) {
          vars[envKey] = value
        }
      })
    })

    try {
      await api.updateLocalEnv(vars)
      setMessage({ type: "success", text: "Configuración guardada. Reinicia el servidor para aplicar cambios." })
    } catch (e: any) {
      setMessage({ type: "error", text: e.message || "Error al guardar" })
    } finally {
      setSaving(false)
    }
  }

  const dismissMessage = () => setMessage(null)

  if (mode !== "local") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="text-center max-w-md">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-amber-100 mb-4">
            <Info className="h-8 w-8 text-amber-600" />
          </div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Configuración solo en modo local</h2>
          <p className="text-gray-500 mb-6">
            La gestión de credenciales OAuth por archivo .env solo está disponible
            cuando <code className="px-1.5 py-0.5 bg-gray-100 rounded text-sm font-mono">SOCIALDROP_MODE=local</code>.
          </p>
          <button
            onClick={() => router.push("/drops")}
            className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition-colors"
          >
            Ir a mis drops
          </button>
        </div>
      </div>
    )
  }

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center">
              <Key className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Configuración Local</h1>
              <p className="text-gray-600">Gestiona credenciales OAuth por plataforma (modo desarrollo)</p>
            </div>
          </div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-green-100 text-green-700 text-sm font-medium">
            <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            Modo local activo
          </div>
        </div>

        {/* Message */}
        {message && (
          <div
            className={cn(
              "mb-6 p-4 rounded-xl border flex items-start gap-3 animate-slide-in",
              message.type === "success"
                ? "bg-green-50 border-green-200 text-green-800"
                : "bg-red-50 border-red-200 text-red-800"
            )}
            role="alert"
          >
            {message.type === "success" ? (
              <CheckCircle2 className="h-5 w-5 flex-shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
            )}
            <div className="flex-1">
              <p className="font-medium">{message.text}</p>
              {message.type === "success" && (
                <p className="text-sm mt-1 opacity-80">
                  Los cambios requieren reiniciar el proceso del backend.
                </p>
              )}
            </div>
            <button onClick={dismissMessage} className="text-gray-400 hover:text-gray-600">
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        {/* Warning */}
        <div className="mb-6 p-4 rounded-xl bg-amber-50 border border-amber-200">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-amber-800">
              <p className="font-medium mb-1">⚠️ Modo desarrollo</p>
              <p>Esta página escribe directamente en el archivo <code className="px-1.5 py-0.5 bg-white rounded font-mono">.env</code> del proyecto.</p>
              <p className="mt-1">No uses esto en producción. En modo cloud, las credenciales se gestionan desde la UI de cada plataforma.</p>
            </div>
          </div>
        </div>

        {/* Platform Cards */}
        <div className="space-y-4">
          {PLATFORM_CONFIG.map((platform) => (
            <PlatformCard
              key={platform.id}
              platform={platform}
              fields={formData[platform.id] || {}}
              onChange={handleChange}
            />
          ))}
        </div>

        {/* Save Button */}
        <div className="mt-8 pt-6 border-t border-gray-200 flex justify-end">
          <button
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-2 px-8 py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
          >
            {saving ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                Guardando...
              </>
            ) : (
              <>
                <Save className="h-5 w-5" />
                Guardar en .env
              </>
            )}
          </button>
        </div>

        {/* Hint */}
        <p className="mt-4 text-center text-sm text-gray-500">
          Después de guardar, reinicia el backend con <code className="px-1.5 py-0.5 bg-gray-100 rounded font-mono">docker-compose restart api</code> o <code className="px-1.5 py-0.5 bg-gray-100 rounded font-mono">railway up</code>
        </p>
      </div>
    </main>
  )
}

interface PlatformCardProps {
  platform: (typeof PLATFORM_CONFIG)[number]
  fields: Record<string, string>
  onChange: (platform: PlatformId, field: string, value: string) => void
}

function PlatformCard({ platform, fields, onChange }: PlatformCardProps) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-100 bg-gray-50">
        <div className="flex items-center gap-3">
          <span className="text-2xl" role="img" aria-label={platform.name}>
            {platform.icon}
          </span>
          <h3 className="text-lg font-semibold text-gray-900 capitalize">{platform.name}</h3>
        </div>
      </div>
      <div className="p-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {platform.fields.map((field) => (
            <div key={field}>
              <label
                htmlFor={`${platform.id}-${field}`}
                className="block text-sm font-medium text-gray-700 mb-1.5"
              >
                {field.replace("_", " ")}
              </label>
              <input
                id={`${platform.id}-${field}`}
                type={field.includes("SECRET") || field.includes("PASSWORD") ? "password" : "text"}
                value={fields[field] || ""}
                onChange={(e) => onChange(platform.id, field, e.target.value)}
                placeholder={`SOCIALDROP_${platform.id.toUpperCase()}_${field}`}
                className="w-full px-4 py-2.5 rounded-xl border border-gray-200 bg-gray-50 focus:border-blue-500 focus:bg-white focus:ring-2 focus:ring-blue-500/20 transition-all text-sm font-mono text-gray-900 placeholder:text-gray-400"
              />
            </div>
          ))}
        </div>
        <p className="mt-4 text-xs text-gray-500 flex items-center gap-1.5">
          <Globe className="h-3.5 w-3.5" />
          Variables: {platform.fields.map((f) => <code key={f} className="px-1.5 py-0.5 bg-gray-100 rounded font-mono text-gray-700 mx-0.5">SOCIALDROP_{platform.id.toUpperCase()}_{f}</code>).join(", ")}
        </p>
      </div>
    </div>
  )
}