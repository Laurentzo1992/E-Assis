import React, { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { apiRequest } from "../services/auth";
import { API_BASE_URL } from "../config";
import "../style.css";

// Page affichee au retour de la page de paiement hebergee CinetPay (return_url, cf.
// api/routers/paiement.py). CinetPay confirme le paiement de son cote via un webhook
// server-to-server (notify_url) qui peut arriver avant, pendant ou juste apres cette redirection
// navigateur - impossible de garantir que l'abonnement soit deja marque "actif" au moment ou
// cette page s'affiche, d'ou le statut "en_attente" ci-dessous plutot qu'une affirmation ferme.
export default function PaymentReturn() {
  const [searchParams] = useSearchParams();
  const entrepriseId = searchParams.get("entreprise_id");

  const [statut, setStatut] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchAbonnement = async () => {
      if (!entrepriseId) {
        setError("Identifiant d'entreprise manquant dans l'URL de retour.");
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
  }, [entrepriseId]);

  return (
    <div className="d-flex align-items-center justify-content-center" style={{ minHeight: "100vh", background: "#f8f9ff" }}>
      <div className="card shadow-sm" style={{ maxWidth: "480px", width: "100%" }}>
        <div className="card-body p-4 text-center">
          <h3 className="titleColor mb-3">Retour du paiement</h3>

          {loading ? (
            <p className="text-muted">Vérification du statut de votre abonnement...</p>
          ) : error ? (
            <div className="alert alert-warning">
              Impossible de vérifier le statut pour le moment : {error}. Si le paiement a bien
              été effectué, il sera pris en compte dès sa confirmation par notre système.
            </div>
          ) : statut.statut === "actif" ? (
            <div className="alert alert-success">
              Paiement confirmé ! Votre abonnement est actif jusqu'au{" "}
              {new Date(statut.date_fin_abonnement).toLocaleDateString("fr-FR")}.
            </div>
          ) : (
            <div className="alert alert-info">
              Votre paiement est en cours de confirmation. Cela peut prendre quelques instants -
              revenez sur votre tableau de bord dans un moment pour voir le statut mis à jour.
            </div>
          )}

          <Link className="btn btn-cta w-100 mt-2" to="/Dashboard">
            Retour au tableau de bord
          </Link>
        </div>
      </div>
    </div>
  );
}
