import { useTheme } from '../lib/ThemeContext'

const OPTIONS = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
  { value: 'system', label: 'Auto' },
] as const

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  return (
    <div className="inline-flex rounded-md border border-line p-0.5 text-xs" role="group" aria-label="Theme">
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          onClick={() => setTheme(option.value)}
          aria-pressed={theme === option.value}
          className={`rounded-[5px] px-2 py-1 transition-colors ${
            theme === option.value ? 'bg-accent-soft text-ink' : 'text-ink-muted hover:text-ink'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
