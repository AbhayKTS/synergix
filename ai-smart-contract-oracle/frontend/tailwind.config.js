/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './src/pages/**/*.{js,jsx,ts,tsx}',
    './src/components/**/*.{js,jsx,ts,tsx}',
    './src/app/**/*.{js,jsx,ts,tsx}',
    './src/**/*.{js,jsx,ts,tsx}'
  ],
  theme: {
    extend: {
      colors: {
        oni: '#111116',
        katana: '#EA2E49',
        neon: '#7034FF',
        frost: '#E9E9E9',
        abyss: '#0D0D0D'
      },
      fontFamily: {
        mono: ['Rajdhani', 'sans-serif'],
        serif: ['Noto Serif JP', 'serif']
      },
      boxShadow: {
        'katana-glow': '0 0 30px rgba(234, 46, 73, 0.45)',
        'neon-ring': '0 0 60px rgba(112, 52, 255, 0.4)'
      }
    }
  },
  plugins: []
};
