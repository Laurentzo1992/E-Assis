import React from "react";
import { Mail } from "lucide-react";
import { Link } from "react-router-dom";

/**
 * Composant affiché après l'inscription pour indiquer que l'email de vérification a été envoyé.
 */
export default function EmailVerificationSent() {
  return (
    <div className="d-flex align-items-center justify-content-center vh-100 custom-bg">
      <div className="text-center p-5 custom-card">
        <Mail size={50} className="mb-3 text-primary-custom" />
        <h2 className="fw-bold text-primary-custom mb-2">
          Vérification d'email envoyée
        </h2>
        <p className="text-muted mb-4">
          Un lien d'activation a été envoyé à votre adresse email.
          Veuillez cliquer sur ce lien pour activer votre compte.
        </p>
        <Link to="/" className="btn btn-primary custom-btn">
          Retour à l'accueil
        </Link>
      </div>
    </div>
  );
}
