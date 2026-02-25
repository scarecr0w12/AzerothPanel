import { useEffect, useState } from 'react'
import { X, CheckCircle, AlertCircle, Info } from 'lucide-react'

export type ToastType = 'success' | 'error' | 'info'

interface Toast {
  id: number
  message: string
  type: ToastType
}

let toastId = 0
let addToast: (message: string, type: ToastType) => void

export function toast(message: string, type: ToastType = 'info') {
  if (addToast) {
    addToast(message, type)
  }
}

export default function ToastContainer() {
  const [toasts, setToasts] = useState<Toast[]>([])

  useEffect(() => {
    addToast = (message: string, type: ToastType) => {
      const id = ++toastId
      setToasts(prev => [...prev, { id, message, type }])
      // Auto-remove after 5 seconds
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id))
      }, 5000)
    }
    return () => {
      addToast = () => {}
    }
  }, [])

  const removeToast = (id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }

  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map(t => (
        <div
          key={t.id}
          className={`flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg max-w-md animate-slide-in ${
            t.type === 'success' ? 'bg-green-600' :
            t.type === 'error' ? 'bg-red-600' : 'bg-blue-600'
          }`}
        >
          {t.type === 'success' && <CheckCircle size={18} className="text-white shrink-0" />}
          {t.type === 'error' && <AlertCircle size={18} className="text-white shrink-0" />}
          {t.type === 'info' && <Info size={18} className="text-white shrink-0" />}
          <span className="text-white text-sm flex-1">{t.message}</span>
          <button
            onClick={() => removeToast(t.id)}
            className="text-white/80 hover:text-white transition-colors"
          >
            <X size={16} />
          </button>
        </div>
      ))}
    </div>
  )
}
