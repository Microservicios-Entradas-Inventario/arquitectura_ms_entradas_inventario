// PostCSS: solo lo usa el módulo de Pagos (src/modules/pagos/pagos.css) para Tailwind.
// Los archivos CSS que no importan Tailwind no cambian.
module.exports = {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};
