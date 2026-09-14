import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth-options"
import { DropsClient } from "./DropsClient"
import { api } from "@/lib/api"

export default async function DropsPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>
}) {
  const session = await getServerSession(authOptions)

  if (!session && process.env.SOCIALDROP_MODE !== "local") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="text-center max-w-md">
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Inicia sesión para ver tus drops</h2>
          <p className="text-gray-500 mb-6">Necesitas estar autenticado para gestionar tu contenido.</p>
          <a
            href="/login?callbackUrl=/drops"
            className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition-colors"
          >
            Iniciar sesión
          </a>
        </div>
      </div>
    )
  }

  const params = await searchParams
  const initialStatus = params.status || "all"

  const drops = await api.getDrops()

  return <DropsClient initialDrops={drops} initialStatus={initialStatus} />
}