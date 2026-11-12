/** Compilar con: npx tailwindcss@3.4.17 -c tailwind/tailwind.config.js -i tailwind/entrada.css -o cotizador/static/cotizador/app.css --minify */
module.exports = {
  content: ["./**/templates/**/*.html", "./**/forms.py"],
  theme: {
    extend: {
      colors: { marca: { DEFAULT: "#1F4E79", sol: "#F59E0B" } },
    },
  },
};
