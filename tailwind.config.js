/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './web/**/*.html',
    './web/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        background: '#1a1a1c',
        surface: '#252529',
        surfaceHighlight: '#323236',
        primary: '#d4b693',
        secondary: '#e4e4e7',
        accent: '#c084fc',
        success: '#86efac',
        danger: '#fda4af',
        textMain: '#f4f4f5',
        textMuted: '#b8b8bc',
      },
      fontFamily: {
        serif: ['Lora', 'serif'],
        sans: ['Mulish', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        '4xl': '2rem',
      },
      animation: {
        'spin-slow': 'spin 20s linear infinite',
      },
    },
  },
  plugins: [],
};
