// ⚠️ ARCHIVO COMPARTIDO ENTRE LOS 9 GRUPOS ⚠️
//
// Este Header aparece en TODAS las páginas de la plataforma.
// NO lo modifiquen por su cuenta desde su módulo: el diseño final
// (logo, links de navegación, estilo) se define en conjunto entre
// los 9 grupos y cualquier cambio se hace vía Pull Request revisado
// por el equipo Platform.
//
// Por ahora este es un placeholder funcional para que puedan probar
// su propia página mientras se define el diseño final del header.

import Logo from "./logo";
import SearchButton from "./boton_busqueda";
import Campana from "./campana";

export default function Header() {
  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: `
        .header-container {
          position: sticky;
          top: 0;
          background-color: #2F4374;
          color: #FFFFFF;
          z-index: 1000;
          display: flex;
          flex-direction: column;
        }
        .header-top {
          height: 64px;
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0 24px;
        }
        .nav-menu {
          display: flex;
          gap: 16px;
          font-size: 14px;
          font-weight: 600;
          font-family: 'Poppins', sans-serif;
          align-items: center;
        }
        .nav-item {
          cursor: pointer;
          padding: 6px 12px;
          border-radius: 999px;
          transition: background-color 0.2s;
        }
        .nav-item.active {
          background-color: rgba(255, 255, 255, 0.18);
        }
        .right-controls {
          display: flex;
          align-items: center;
          gap: 16px;
        }
        .avatar-wrapper {
          width: 44px;
          height: 44px;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
        }
        .avatar-circle {
          width: 32px;
          height: 32px;
          background-color: #FFFFFF;
          color: #2F4374;
          border-radius: 999px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 600;
          font-size: 12px;
          font-family: 'Inter', sans-serif;
        }
        @media (max-width: 1024px) {
          .mobile-scroll-container {
            width: 100%;
            overflow-x: auto;
            scrollbar-width: none;
            -ms-overflow-style: none;
            padding: 0 24px 12px 24px;
          }
          .mobile-scroll-container::-webkit-scrollbar {
            display: none;
          }
          .desktop-nav {
            display: none;
          }
        }
        @media (min-width: 1025px) {
          .mobile-scroll-container {
            display: none;
          }
        }
      `}} />
      <header className="header-container">
        <div className="header-top">
          <div style={{ display: "flex", alignItems: "center", gap: "24px" }}>
            <Logo />
            <nav className="nav-menu desktop-nav">
              <span className="nav-item active">Inicio</span>
              <span className="nav-item">Mis eventos</span>
              <span className="nav-item">Promociones</span>
              <span className="nav-item">Configuración</span>
              <span className="nav-item">Mi cuenta</span>
            </nav>
          </div>
          <div className="right-controls">
            <SearchButton />
            <Campana />
            <div className="avatar-wrapper">
              <div className="avatar-circle">MC</div> 
            </div>
          </div>
        </div>
        <div className="mobile-scroll-container">
          <nav className="nav-menu">
            <span className="nav-item active">Inicio</span>
            <span className="nav-item">Mis eventos</span>
            <span className="nav-item">Promociones</span>
            <span className="nav-item">Configuración</span>
            <span className="nav-item">Mi cuenta</span>
          </nav>
        </div>
      </header>
    </>
  );
}