import React from "react";
import { useTranslation } from "react-i18next";
import { Mail } from "lucide-react";
import { Link } from "react-router-dom";

/**
 * Composant affiché après l'inscription pour indiquer que l'email de vérification a été envoyé.
 */
export default function EmailVerificationSent() {
  const { t } = useTranslation();
  return (
    <div className="d-flex align-items-center justify-content-center vh-100 custom-bg">
      <div className="text-center p-5 custom-card">
        <Mail size={50} className="mb-3 text-primary-custom" />
        <h2 className="fw-bold text-primary-custom mb-2">
          {t("emailVerificationSent.title")}
        </h2>
        <p className="text-muted mb-4">{t("emailVerificationSent.text")}</p>
        <Link to="/" className="btn btn-primary custom-btn">
          {t("emailVerificationSent.backHome")}
        </Link>
      </div>
    </div>
  );
}
