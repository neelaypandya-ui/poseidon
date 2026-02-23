import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          900: '#050D1A',
          800: '#0A1628',
          700: '#0F1F35',
          600: '#162A45',
          500: '#1E3A5F',
        },
      },
    },
  },
  plugins: [],
} satisfies Config
