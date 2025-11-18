// In tailwind.config.js

import headlessui from '@headlessui/tailwindcss'

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}', // <-- This is the magic line
  ],
  theme: {
    extend: {},
  },
  plugins: [
    headlessui,
  ],
}