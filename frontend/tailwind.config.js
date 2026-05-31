/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: '#1a1b26',
          fg: '#a9b1d6',
          green: '#9ece6a',
          blue: '#7aa2f7',
          yellow: '#e0af68',
          red: '#f7768e',
          purple: '#bb9af7',
          cyan: '#7dcfff',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
}
