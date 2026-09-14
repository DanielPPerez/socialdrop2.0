"use client"

import { useState } from "react"
import { PlatformStatus, PlatformConnection } from "@/lib/api"
import { CheckCircle2, AlertCircle, ExternalLink, Loader2, Trash2 } from "lucide-react"
import { cn } from "@/lib/utils"

interface PlatformCardProps {
  platform: PlatformStatus
  connection: PlatformConnection | undefined
  onConnect: (platform: string) => void
  onDisconnect: (platform: string) => void
}

export function PlatformCard({ platform, connection, onConnect, onDisconnect }: PlatformCardProps) {
  const [disconnecting, setDisconnecting] = useState(false)
  const [showDisconnectConfirm, setShowDisconnectConfirm] = useState(false)

  const isConnected = !!connection
  const displayName = connection?.account_label || platform.platform
  const connectedAt = connection ? new Date(connection.connected_at).toLocaleDateString("es-ES", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }) : null

  const handleDisconnect = async () => {
    setDisconnecting(true)
    try {
      await onDisconnect(platform.platform)
    } catch (e) {
      console.error("Disconnect failed:", e)
    } finally {
      setDisconnecting(false)
      setShowDisconnectConfirm(false)
    }
  }

  return (
    <div className="group relative bg-white rounded-2xl border border-gray-100 shadow-sm hover:shadow-md transition-all duration-300 p-6">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={cn(
            "w-12 h-12 rounded-xl flex items-center justify-center",
            isConnected ? "bg-green-100 text-green-600" : "bg-gray-100 text-gray-500"
          )}>
            {isConnected ? (
              <CheckCircle2 className="h-6 w-6" />
            ) : (
              <span className="font-semibold text-lg">{platform.platform.charAt(0).toUpperCase()}</span>
            )}
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 text-lg capitalize">{platform.platform}</h3>
            <p className="text-sm text-gray-500">
              {isConnected ? `Conectado como ${displayName}` : "No conectado"}
            </p>
          </div>
        </div>
        {isConnected && (
          <button
            onClick={() => setShowDisconnectConfirm(true)}
            disabled={disconnecting}
            className="p-2 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors disabled:opacity-50"
            aria-label={`Desconectar ${platform.platform}`}
          >
            <Trash2 className="h-5 w-5" />
          </button>
        )}
      </div>

      <div className="space-y-3 mb-4">
        <div className={cn(
          "flex items-center gap-2 text-sm",
          isConnected ? "text-green-700 bg-green-50" : "text-gray-500 bg-gray-50"
        )}>
          <span className={cn(
            "w-2 h-2 rounded-full",
            isConnected ? "bg-green-500" : "bg-gray-300"
          )} />
          <span className="font-medium">
            {isConnected ? "Conectado" : "No conectado"}
          </span>
          {isConnected && connectedAt && (
            <span className="text-gray-500 ml-2">· Conectado el {connectedAt}</span>
          )}
        </div>

        {platform.detail && (
          <p className="text-xs text-gray-500 bg-gray-50 px-3 py-2 rounded-lg font-mono">
            {platform.detail}
          </p>
        )}

        {platform.configured && !platform.authenticated && !isConnected && (
          <div className="flex items-center gap-2 text-sm text-amber-700 bg-amber-50 px-3 py-2 rounded-lg">
            <AlertCircle className="h-4 w-4" />
            <span>Configurado pero no autenticado</span>
          </div>
        )}
      </div>

      <div className="flex gap-3 pt-4 border-t border-gray-100">
        {isConnected ? (
          <button
            onClick={handleDisconnect}
            disabled={disconnecting}
            className="flex-1 py-2.5 px-4 rounded-xl border border-gray-200 text-gray-700 font-medium hover:bg-gray-50 hover:border-gray-300 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {disconnecting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Desconectando...
              </>
            ) : (
              <>
                <Trash2 className="h-4 w-4" />
                Desconectar
              </>
            )}
          </button>
        ) : (
          <button
            onClick={() => onConnect(platform.platform)}
            disabled={platform.configured && !platform.authenticated}
            className="flex-1 py-2.5 px-4 rounded-xl bg-blue-600 text-white font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {platform.configured && !platform.authenticated ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Autenticando...
              </>
            ) : (
              <>
                <ExternalLink className="h-4 w-4" />
                Conectar
              </>
            )}
          </button>
        )}
      </div>

      {showDisconnectConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-2xl p-6 max-w-md w-full shadow-xl">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">¿Desconectar {platform.platform}?</h3>
            <p className="text-gray-600 mb-6">
              Se revocará el token de acceso y se eliminará la conexión. Tendrás que volver a conectar la cuenta para publicar.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowDisconnectConfirm(false)}
                className="px-4 py-2 rounded-xl border border-gray-200 text-gray-700 font-medium hover:bg-gray-50 transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleDisconnect}
                disabled={disconnecting}
                className="px-4 py-2 rounded-xl bg-red-600 text-white font-medium hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {disconnecting ? "Desconectando..." : "Desconectar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}