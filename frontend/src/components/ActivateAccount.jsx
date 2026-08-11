import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { API_BASE_URL } from "../config";

export default function ActivateAccount() {
  const { token } = useParams();
  const [message, setMessage] = useState("Activation en cours...");
  const navigate = useNavigate();

    useEffect(() => {
    fetch(`${API_BASE_URL}/api/auth/activate/${token}/`)
        .then(async (res) => {
        const data = await res.json();
        console.log("Réponse API:", data);

        if (res.ok) {
            setMessage(data.message || "Votre compte a été activé avec succès.");
            setTimeout(() => navigate("/connexion"), 3000);
        } else {
            if (data.error && data.error.includes("Activé")) {
            setMessage("Votre compte est activé. Vous pouvez vous connecter.");
            setTimeout(() => navigate("/connexion"), 3000);
            } else {
            setMessage(data.error || "Le lien d'activation est invalide ou expiré.");
            }
        }
        })
        .catch(() => setMessage("Erreur lors de l'activation du compte."));
    }, [token, navigate]);

  return (
    <div className="d-flex align-items-center justify-content-center p-4 custom-bg">
      <div className="container text-center">
        <div className="custom-card p-4 p-sm-5">
          <h2 className="h2 fw-bold text-primary-custom mb-3">Activation du compte</h2>
          <p className="text-primary-custom opacity-75">{message}</p>
        </div>
      </div>
    </div>
  );
}
