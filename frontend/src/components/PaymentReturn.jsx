import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams, Link } from "react-router-dom";
import { apiRequest } from "../services/auth";
import { API_BASE_URL } from "../config";
import "../style.css";

// Locale de formatage de date : le mooré n'a pas de locale Intl dediee, on retombe sur le
// francais (repli raisonnable, meme convention que GOOGLE_LOCALES dans Inscription.jsx).
const DATE_LOCALES = { fr: "fr-FR", en: "en-US", mos: "fr-FR" };

// Page affichee au retour de la page de paiement hebergee CinetPay (return_url, cf.
// api/routers/paiement.py). CinetPay confirme le paiement de son cote via un webhook
// server-to-server (notify_url) qui peut arriver avant, pendant ou juste apres cette redirection
// navigateur - impossible de garantir que l'abonnement soit deja marque "actif" au moment ou
// cette page s'affiche, d'ou le statut "en_attente" ci-dessous plutot qu'une affirmation ferme.
export default function PaymentReturn() {
  const { t, i18n } = useTranslation();
  const [searchParams] = useSearchParams();
  const entrepriseId = searchParams.get("entreprise_id");

  const [statut, setStatut] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchAbonnement = async () => {
      if (!entrepriseId) {
        setError(t("paymentReturn.missingEntreprise"));
        setLoading(false);
        return;
      }
      try {
        const response = await apiRequest(
          `${API_BASE_URL}/api/paiement/abonnement/${entrepriseId}/`
        );
        if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);
        const data = await response.json();
        setStatut(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchAbonnement();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entrepriseId]);

  return (
    <div className="d-flex align-items-center justify-content-center" style={{ minHeight: "100vh", background: "#f8f9ff" }}>
      <div className="card shadow-sm" style={{ maxWidth: "480px", width: "100%" }}>
        <div className="card-body p-4 text-center">
          <h3 className="titleColor mb-3">{t("paymentReturn.title")}</h3>

          {loading ? (
            <p className="text-muted">{t("paymentReturn.loading")}</p>
          ) : error ? (
            <div className="alert alert-warning">
              {t("paymentReturn.errorPrefix", { error })}
            </div>
          ) : statut.statut === "actif" ? (
            <div className="alert alert-success">
              {t("paymentReturn.successPrefix", {
                date: new Date(statut.date_fin_abonnement).toLocaleDateString(
                  DATE_LOCALES[i18n.language] || "fr-FR"
                ),
              })}
            </div>
          ) : (
            <div className="alert alert-info">{t("paymentReturn.pending")}</div>
          )}

          <Link className="btn btn-cta w-100 mt-2" to="/Dashboard">
            {t("paymentReturn.backToDashboard")}
          </Link>
        </div>
      </div>
    </div>
  );
}
