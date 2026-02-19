/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // AzerothPanel dark theme palette
        panel: {
          bg:        '#0f1117',
          surface:   '#1a1d27',
          border:    '#2a2d3e',
          hover:     '#252839',
          muted:     '#6b7280',
        },
        brand: {
          DEFAULT:   '#7c6afc',
          hover:     '#6a58f0',
          light:     '#a899fd',
        },
        success:  '#22c55e',
        warning:  '#f59e0b',
        danger:   '#ef4444',
        info:     '#3b82f6',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}

