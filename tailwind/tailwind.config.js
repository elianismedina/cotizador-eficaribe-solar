/** Compilar con: npx tailwindcss@3.4.17 -c tailwind/tailwind.config.js -i tailwind/entrada.css -o cotizador/static/cotizador/app.css --minify */
// Los colores de marca vienen de variables CSS que define base.html a partir de Configuración > Empresa.
module.exports = {
  content: ["./**/templates/**/*.html", "./**/forms.py"],
  theme: {
    extend: {
      colors: {
        marca: {
          DEFAULT: "rgb(var(--marca) / <alpha-value>)",
          oscuro: "rgb(var(--marca-oscuro) / <alpha-value>)",
          sol: "rgb(var(--marca-sol) / <alpha-value>)",
        },
      },
    },
  },
};
