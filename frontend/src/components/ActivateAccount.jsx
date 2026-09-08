import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams, useNavigate } from "react-router-dom";
import { API_BASE_URL } from "../config";

export default function ActivateAccount() {
  const { t } = useTranslation();
  const { token } = useParams();
  const [message, setMessage] = useState(t("activation.inProgress"));
  const navigate = useNavigate();

    useEffect(() => {
    fetch(`${API_BASE_URL}/api/auth/activate/${token}/`)
        .then(async (res) => {
        const data = await res.json();
        console.log("Réponse API:", data);

        if (res.ok) {
            setMessage(data.message || t("activation.success"));
            setTimeout(() => navigate("/connexion"), 3000);
        } else {
            if (data.error && data.error.includes("Activé")) {
            setMessage(t("activation.alreadyActive"));
            setTimeout(() => navigate("/connexion"), 3000);
            } else {
            setMessage(data.error || t("activation.genericError"));
            }
        }
        })
        .catch(() => setMessage(t("activation.fetchError")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [token, navigate]);

  return (
    <div className="d-flex align-items-center justify-content-center p-4 custom-bg">
      <div className="container text-center">
        <div className="custom-card p-4 p-sm-5">
          <h2 className="h2 fw-bold text-primary-custom mb-3">{t("activation.title")}</h2>
          <p className="text-primary-custom opacity-75">{message}</p>
        </div>
      </div>
    </div>
  );
}
