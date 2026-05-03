/** @type {import(''tailwindcss'').Config} */
export default {
  content: [''./index.html'', ''./src/**/*.{js,ts,jsx,tsx}''],
  theme: {
    extend: {
      colors: {
        pitch: { 900: ''#0a1628'', 800: ''#0d1f3c'', 700: ''#112347'', 600: ''#1a3460'' },
        electric: { 400: ''#38bdf8'', 500: ''#0ea5e9'', 600: ''#0284c7'' },
        gold: { 300: ''#fde68a'', 400: ''#fbbf24'', 500: ''#f59e0b'', 600: ''#d97706'' },
        elite: { from: ''#a78bfa'', to: ''#ec4899'' },
      },
      fontFamily: {
        display: [''Barlow Condensed'', ''sans-serif''],
        body: [''Inter'', ''sans-serif''],
      },
      animation: {
        ''card-shine'': ''shine 2s linear infinite'',
        ''pulse-glow'': ''pulse-glow 2s ease-in-out infinite'',
        ''level-up'': ''level-up 0.6s ease-out'',
        ''xp-fill'': ''xp-fill 1s ease-out forwards'',
      },
      keyframes: {
        shine: { ''0%'': { backgroundPosition: ''-200% 0'' }, ''100%'': { backgroundPosition: ''200% 0'' } },
        ''pulse-glow'': { ''0%,100%'': { boxShadow: ''0 0 20px rgba(167,139,250,0.3)'' }, ''50%'': { boxShadow: ''0 0 40px rgba(167,139,250,0.8)'' } },
        ''level-up'': { ''0%'': { transform: ''scale(0.5)'', opacity: ''0'' }, ''60%'': { transform: ''scale(1.2)'' }, ''100%'': { transform: ''scale(1)'', opacity: ''1'' } },
        ''xp-fill'': { ''0%'': { width: ''0%'' }, ''100%'': { width: ''var(--xp-percent)'' } },
      },
    },
  },
  plugins: [],
};
