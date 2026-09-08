import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams, useNavigate, Link } from "react-router-dom";
import { API_BASE_URL } from "../config";

const ResetPasswordConfirm = () => {
  const { t } = useTranslation();
  const { uidb64, token } = useParams();
  const navigate = useNavigate();
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (newPassword !== confirmPassword) {
      setError(t("resetPassword.errors.mismatch"));
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/reset-password-confirm/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ uidb64, token, new_password: newPassword }),
      });
      const data = await response.json();

      if (response.ok) {
        setSuccess(true);
        setTimeout(() => navigate("/Connexion"), 3000);
      } else {
        const detail = data.new_password || data.detail;
        setError(Array.isArray(detail) ? detail.join(" ") : detail || t("resetPassword.errors.invalidLink"));
      }
    } catch (err) {
      console.error("Erreur lors de la réinitialisation du mot de passe:", err);
      setError(t("resetPassword.errors.network"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="connexion-wrapper d-flex justify-content-center align-items-center min-vh-100 py-5">
      <div className="connexion-container">
        <div className="connexion-card p-4">
          <div className="text-center mb-4">
            <h2 className="connexion-title mb-2">{t("resetPassword.title")}</h2>
            <p className="connexion-subtitle">{t("resetPassword.subtitle")}</p>
          </div>

          {success ? (
            <p className="text-center" style={{ color: "green" }}>
              {t("resetPassword.success")}
            </p>
          ) : (
            <form onSubmit={handleSubmit}>
              {error && (
                <div className="alert alert-danger mb-3" role="alert">
                  {error}
                </div>
              )}

              <div className="mb-3">
                <div className="input-group connexion-input-group">
                  <input
                    type={showPassword ? "text" : "password"}
                    className="form-control connexion-input"
                    placeholder={t("resetPassword.placeholders.newPassword")}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                  />
                  <button
                    type="button"
                    className="btn connexion-password-toggle"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? t("resetPassword.hide") : t("resetPassword.show")}
                  </button>
                </div>
              </div>

              <div className="mb-4">
                <div className="input-group connexion-input-group">
                  <input
                    type={showPassword ? "text" : "password"}
                    className="form-control connexion-input"
                    placeholder={t("resetPassword.placeholders.confirmPassword")}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                  />
                </div>
              </div>

              <button
                type="submit"
                className="btn connexion-btn-primary w-100 mb-4"
                disabled={submitting}
              >
                {submitting ? t("resetPassword.submit.loading") : t("resetPassword.submit.default")}
              </button>
            </form>
          )}

          <div className="text-center">
            <p className="connexion-signup-text">
              <Link className="connexion-signup-link" to="/Connexion">
                {t("resetPassword.backToLogin")}
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ResetPasswordConfirm;
