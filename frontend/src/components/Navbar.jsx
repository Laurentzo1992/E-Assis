import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import LanguageSwitcher from "./LanguageSwitcher";

export default function Navbar() {
  const { t } = useTranslation();

  return (
    <nav className="navbar navbar-expand-lg navbar-light  Navbar">
      <div className="container-fluid">
        <Link className="navbar-brand text-white fw-bold" to="/">
          {t("nav.brand")}
        </Link>
        <button
          className="navbar-toggler bg-light"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#navbarNav"
          aria-controls="navbarNav"
          aria-expanded="false"
          aria-label={t("nav.toggleNavigation")}
        >
          <span className="navbar-toggler-icon "></span>
        </button>
        <div className="collapse navbar-collapse" id="navbarNav">
          <ul className="navbar-nav ms-auto align-items-lg-center">
            <li className="nav-item">
              <a className="nav-link text-white" href="#tarifs">
                {t("nav.tarifs")}
              </a>
            </li>
            <li className="nav-item">
              <Link className="nav-link text-white" to="/connexion">
                {t("nav.connexion")}
              </Link>
            </li>
            <li className="nav-item">
              <Link className="nav-link text-white" to="/inscription">
                {t("nav.inscription")}
              </Link>
            </li>
            <li className="nav-item">
              <LanguageSwitcher />
            </li>
          </ul>
        </div>
      </div>
    </nav>
  );
}
