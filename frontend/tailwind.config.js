/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        night: {
          50: '#f5f3ff',  100: '#ede9fe', 200: '#ddd6fe', 300: '#c4b5fd',
          400: '#a78bfa', 500: '#8b5cf6', 600: '#7c3aed', 700: '#6d28d9',
          800: '#5b21b6', 900: '#4c1d95', 950: '#1e1b4b',
        },
      },
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
      boxShadow: {
        'soft': '0 4px 20px -2px rgba(76, 29, 149, 0.15)',
        'glow': '0 0 40px -10px rgba(139, 92, 246, 0.5)',
      },
    },
  },
  plugins: [],
}
