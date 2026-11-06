// ⚠️ ARCHIVO COMPARTIDO ENTRE LOS 9 GRUPOS ⚠️
//
// Igual que el Header: aparece en TODAS las páginas. Se define en
// conjunto entre los 9 grupos y se modifica solo vía Pull Request.
//
// Placeholder funcional mientras se define el diseño final.

export default function Footer() {
  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: `
        .footer-container {
          background-color: #2F4374;
          color: #FFFFFF;
          padding: 1.5rem 2rem;
          margin-top: 3rem;
          display: flex;
          justify-content: center;
          align-items: center;
          font-family: 'Inter', sans-serif;
          font-size: 14px;
        }
        .footer-content {
          display: flex;
          gap: 24px;
          align-items: center;
        }
        .footer-text {
          font-weight: 600;
        }
        .footer-link {
          cursor: pointer;
        }
        .footer-separator {
          border-left: 1px solid #FFFFFF;
          height: 16px;
        }
        @media (max-width: 640px) {
          .footer-content {
            flex-direction: column;
            gap: 16px;
          }
          .footer-separator {
            display: none;
          }
        }
      `}} />
      <footer className="footer-container">
        <div className="footer-content">
          <span className="footer-text">TICKET-U © 2026</span>
          <div className="footer-separator"></div>
          <span className="footer-link">Centro de Ayuda</span>
          <div className="footer-separator"></div>
          <span className="footer-link">Términos de Servicio</span>
        </div>
      </footer>
    </>
  );
}