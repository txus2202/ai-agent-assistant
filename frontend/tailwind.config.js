/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        space: {
          950: '#05070c',
          900: '#070b12',
          850: '#0b111c',
          800: '#0f1726',
          750: '#141f33',
          700: '#1a2942',
        },
        neon: {
          green:      '#00ff9d',
          cyan:       '#00e5ff',
          blue:       '#2979ff',
          amber:      '#ffd000',
          red:        '#ef4444',     // adjusted to match stitch prototype exactly
          purple:     '#b347ff',
          orange:     '#ff8800',
          darkgreen:  '#00ff9d',     // Senior Architect
          lightgreen: '#22c55e',     // Innovator
          darkblue:   '#1d4ed8',     // Learning Agent
        }
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'Liberation Mono', 'Courier New', 'monospace'],
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      }
    }
  },
  plugins: [],
}
