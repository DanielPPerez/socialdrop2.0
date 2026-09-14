import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth-options"
import { SettingsClient } from "./SettingsClient"
import { api } from "@/lib/api"

export default async function SettingsPage() {
  const session = await getServerSession(authOptions)

  if (!session && process.env.SOCIALDROP_MODE !== "local") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="text-center max-w-md">
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Inicia sesión para ver configuración</h2>
          <p className="text-gray-500 mb-6">Necesitas estar autenticado para gestionar la configuración.</p>
          <a
            href="/login?callbackUrl=/settings"
            className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition-colors"
          >
            Iniciar sesión
          </a>
        </div>
      </div>
    )
  }

  // Get mode server-side for initial render
  let mode: "local" | "cloud" = "cloud"
  try {
    const res = await api.getMode()
    mode = res.mode
  } catch {
    mode = "cloud"
  }

  return <SettingsClient initialMode={mode} />
}