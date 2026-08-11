import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Footer from "./components/Footer";
import { Check } from "lucide-react";
import { fetchTarif } from "./services/tarif";
import "./style.css";

const AVANTAGES = [
  "Veille automatique et quotidienne des marchés publics du Burkina Faso",
  "Alertes personnalisées selon vos domaines et secteurs d'activité",
  "Suivi des résultats d'attribution de vos candidatures",
  "Accès illimité aux bulletins et documents officiels",
  "Gestion de plusieurs entreprises depuis un seul compte",
];

export default function Tarifs() {
  const [tarif, setTarif] = useState(null);

  useEffect(() => {
    fetchTarif()
      .then(setTarif)
      .catch((error) => console.error("Erreur lors du chargement du tarif :", error));
  }, []);

  return (
    <>
      <nav className="navbar navbar-expand-lg navbar-light Navbar">
        <div className="container-fluid">
          <Link className="navbar-brand text-white fw-bold" to="/">
            Veille Marchés
          </Link>
          <button
            className="navbar-toggler bg-light"
            type="button"
            data-bs-toggle="collapse"
            data-bs-target="#navbarNavTarifs"
            aria-controls="navbarNavTarifs"
            aria-expanded="false"
            aria-label="Toggle navigation"
          >
            <span className="navbar-toggler-icon"></span>
          </button>
          <div className="collapse navbar-collapse" id="navbarNavTarifs">
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

      <section className="py-5" style={{ background: "#f8f9ff" }}>
        <div className="container py-4">
          <div className="text-center mb-5">
            <h1 className="titleColor">Un tarif simple, par entreprise</h1>
            <p className="text-muted fs-5">
              Essayez gratuitement, puis continuez avec un abonnement annuel sans surprise.
            </p>
          </div>

          <div className="row justify-content-center">
            <div className="col-lg-5 col-md-8 mb-4">
              <div className="card h-100 shadow-sm">
                <div className="card-body p-4 text-center">
                  <h3 className="titleColor">Essai gratuit</h3>
                  <p className="display-6 fw-bold mb-0">
                    {tarif ? `${tarif.essai_gratuit_jours} jours` : "…"}
                  </p>
                  <p className="text-muted">Sans engagement, sans carte bancaire</p>
                  <Link className="btn btn-cta w-100 mt-3" to="/inscription">
                    Commencer gratuitement
                  </Link>
                </div>
              </div>
            </div>

            <div className="col-lg-5 col-md-8 mb-4">
              <div className="card h-100 shadow" style={{ border: "2px solid var(--orange)" }}>
                <div className="card-body p-4 text-center">
                  <h3 className="titleColor">Abonnement annuel</h3>
                  <p className="display-6 fw-bold mb-0">
                    {tarif ? `${Number(tarif.prix_annuel).toLocaleString("fr-FR")} ${tarif.devise}` : "…"}
                  </p>
                  <p className="text-muted">par entreprise, par an</p>
                  <Link className="btn btn-cta w-100 mt-3" to="/inscription">
                    Démarrer mon essai
                  </Link>
                </div>
              </div>
            </div>
          </div>

          <div className="row justify-content-center mt-4">
            <div className="col-lg-8">
              <div className="card shadow-sm">
                <div className="card-body p-4">
                  <h5 className="titleColor mb-3">Inclus dans l'abonnement</h5>
                  <ul className="list-unstyled mb-0">
                    {AVANTAGES.map((avantage) => (
                      <li key={avantage} className="d-flex align-items-start mb-2">
                        <Check size={20} className="text-success me-2 flex-shrink-0 mt-1" />
                        <span>{avantage}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
              <p className="text-muted text-center mt-3">
                Paiement sécurisé par Mobile Money (Orange Money, Moov Money) ou carte bancaire.
              </p>
            </div>
          </div>
        </div>
      </section>

      <Footer />
    </>
  );
}
