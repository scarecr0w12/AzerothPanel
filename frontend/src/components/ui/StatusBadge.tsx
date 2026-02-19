import clsx from 'clsx'

type Status = 'online' | 'offline' | 'starting' | 'stopping' | 'error'

const STYLE: Record<Status, string> = {
  online:   'bg-success/15 text-success border border-success/30',
  offline:  'bg-danger/15 text-danger border border-danger/30',
  starting: 'bg-warning/15 text-warning border border-warning/30',
  stopping: 'bg-warning/15 text-warning border border-warning/30',
  error:    'bg-danger/15 text-danger border border-danger/30',
}

const DOT: Record<Status, string> = {
  online:   'bg-success animate-pulse',
  offline:  'bg-danger',
  starting: 'bg-warning animate-pulse',
  stopping: 'bg-warning animate-pulse',
  error:    'bg-danger',
}

interface Props {
  status: Status
  label?: string
  className?: string
}

export default function StatusBadge({ status, label, className }: Props) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium',
        STYLE[status],
        className
      )}
    >
      <span className={clsx('w-1.5 h-1.5 rounded-full', DOT[status])} />
      {label ?? status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  )
}

