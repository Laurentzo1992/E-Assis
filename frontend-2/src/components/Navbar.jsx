import { Link } from "react-router-dom";
export default function Navbar() {
  return (
    <>
      <nav className="navbar navbar-expand-lg navbar-light  Navbar">
        <div className="container-fluid">
          <a className="navbar-brand" href="#"></a>
          <button
            className="navbar-toggler bg-light"
            type="button"
            data-bs-toggle="collapse"
            data-bs-target="#navbarNav"
            aria-controls="navbarNav"
            aria-expanded="false"
            aria-label="Toggle navigation"
          >
            <span className="navbar-toggler-icon "></span>
          </button>
          <div className="collapse navbar-collapse" id="navbarNav">
            <ul className="navbar-nav ms-auto">
              <li className="nav-item">
                <Link className="nav-link text-white" to="/connexion">
                  Se connecter
                </Link>
              </li>
              <li className="nav-item">
                <Link className="nav-link text-white" to="/inscription">
                  Inscription
                </Link>
              </li>
            </ul>
          </div>
        </div>
      </nav>
      <header className="header-gradient">
        {/* Triangle en bas à gauche */}
        <svg
          className="triangle bottom-left"
          width="250"
          height="250"
          viewBox="0 0 358 381"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M358 381C178.8 275.8 44.6667 83.1667 0 0V381H358Z"
            fill="#D9D9D9"
          />
        </svg>

        {/* Triangle en haut à droite */}
        <svg
          className="triangle top-right"
          width="250"
          height="250"
          viewBox="0 0 358 381"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M358 381C178.8 275.8 44.6667 83.1667 0 0V381H358Z"
            fill="#D9D9D9"
          />
        </svg>

        {/* Contenu texte */}
        <h1>
          Ne manquez plus aucune opportunité de marché public au Burkina Faso
        </h1>
        <h3 className="fs-5">
          La plateforme sécurisée, fiable et ultra-rapide qui scanne, classe et
          vous alerte en temps réel
        </h3>
        <button className="btn  mt-3 ">
          <Link className="nav-link text-white" to="/inscription">
            Démarrer ma veille
          </Link>
        </button>
      </header>
    </>
  );
}
