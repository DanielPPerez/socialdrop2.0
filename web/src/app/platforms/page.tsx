import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth-options"
import { PlatformCard } from "@/components/PlatformCard"
import { api } from "@/lib/api"
import { Loader2, AlertCircle } from "lucide-react"
import { Suspense } from "react"

async function fetchPlatformsData() {
  const [platforms, connections] = await Promise.all([
    api.getPlatforms(),
    api.getConnections(),
  ])
  return { platforms, connections }
}

async function PlatformsContent() {
  const { platforms, connections } = await fetchPlatformsData()

  const connectionsMap = new Map(connections.map((c) => [c.platform, c]))

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Plataformas conectadas</h1>
        <p className="text-gray-600">
          Gestiona tus conexiones OAuth por plataforma. Cada conexión es personal y persiste entre sesiones.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {platforms.map((platform) => (
          <PlatformCard
            key={platform.platform}
            platform={platform}
            connection={connectionsMap.get(platform.platform)}
            onConnect={async (platformName) => {
              try {
                const { authorize_url } = await api.startAuth(platformName)
                window.location.href = authorize_url
              } catch (e) {
                console.error("Auth start failed:", e)
                alert("Error al iniciar autenticación")
              }
            }}
            onDisconnect={async (platformName) => {
              try {
                await api.deleteConnection(platformName)
                window.location.reload()
              } catch (e) {
                console.error("Disconnect failed:", e)
                alert("Error al desconectar")
              }
            }}
          />
        ))}
      </div>

      {platforms.length === 0 && (
        <div className="text-center py-16">
          <AlertCircle className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No hay plataformas disponibles</h3>
          <p className="text-gray-500">Configura las credenciales OAuth en el backend para habilitar plataformas.</p>
        </div>
      )}
    </div>
  )
}

function PlatformsLoading() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <div className="h-8 w-48 bg-gray-200 rounded animate-pulse mb-4" />
        <div className="h-4 w-64 bg-gray-200 rounded animate-pulse" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-white rounded-2xl border border-gray-100 p-6 animate-pulse">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-xl bg-gray-200" />
              <div>
                <div className="h-5 w-32 bg-gray-200 rounded mb-2" />
                <div className="h-4 w-24 bg-gray-200 rounded" />
              </div>
            </div>
            <div className="space-y-3 mb-4">
              <div className="h-5 bg-gray-200 rounded w-3/4" />
              <div className="h-4 bg-gray-200 rounded w-full" />
            </div>
            <div className="h-10 bg-gray-200 rounded mt-4" />
          </div>
        ))}
      </div>
    </div>
  )
}

export default async function PlatformsPage() {
  const session = await getServerSession(authOptions)

  if (!session && process.env.SOCIALDROP_MODE !== "local") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="text-center max-w-md">
          <Loader2 className="h-12 w-12 text-blue-600 animate-spin mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Redirigiendo al login...</h2>
          <p className="text-gray-500">Necesitas iniciar sesión para gestionar tus plataformas.</p>
        </div>
      </div>
    )
  }

  return (
    <main className="min-h-screen bg-gray-50">
      <Suspense fallback={<PlatformsLoading />}>
        <PlatformsContent />
      </Suspense>
    </main>
  )
}