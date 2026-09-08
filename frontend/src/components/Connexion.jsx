import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { storeTokens, setNavigateInstance } from "../services/auth";
import { API_BASE_URL } from "../config";

const Connexion = () => {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [showResendEmailButton, setShowResendEmailButton] = useState(false);
  const [resendMessage, setResendMessage] = useState("");
  // Suit separement le statut du dernier resend (succes/erreur/en cours) - ne pas deduire
  // l'etat depuis le texte affiche (ex. recherche de "succès" en dur) car ce texte est desormais
  // traduit et ne contiendrait plus ce mot dans les autres langues.
  const [resendStatus, setResendStatus] = useState(null); // 'success' | 'error' | null
  const [forgotPasswordMessage, setForgotPasswordMessage] = useState("");
  const navigate = useNavigate();

  // IMPORTANT: Passer l'instance de navigate au service d'authentification
  React.useEffect(() => {
    setNavigateInstance(navigate);
  }, [navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setResendMessage("");
    setResendStatus(null);
    setShowResendEmailButton(false);

    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/login/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email,
          password,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        const { access, refresh } = data;

        // Utilisez storeTokens ici
        storeTokens(access, refresh, rememberMe);

        navigate("/dashboard");
      } else {
        const errorData = await response.json();
        // Vérifier si l'erreur est liée à la vérification de l'email
        if (
          errorData.detail &&
          errorData.detail.includes("Veuillez vérifier votre adresse email")
        ) {
          setError(t("connexion.errors.notVerified"));
          setShowResendEmailButton(true); // Afficher le bouton de renvoi d'email
        } else {
          const errorMessage =
            errorData.detail ||
            errorData.non_field_errors ||
            t("connexion.errors.invalidCredentials");
          setError(errorMessage);
        }
        console.error("Erreur de connexion:", errorData);
      }
    } catch (err) {
      console.error("Erreur réseau ou autre:", err);
      setError(t("connexion.errors.networkError"));
    }
  };

  const handleResendVerificationEmail = async () => {
    setResendMessage(t("connexion.resend.sending"));
    setResendStatus(null);
    try {
      // Utilisez l'API de demande de réinitialisation de mot de passe pour renvoyer l'email de vérification
      // Le backend doit être configuré pour gérer ce cas pour les emails non vérifiés.
      const response = await fetch(
        `${API_BASE_URL}/api/auth/reset-password-request/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ email }),
        }
      );

      if (response.ok) {
        setResendMessage(t("connexion.resend.success"));
        setResendStatus("success");
      } else {
        const errorData = await response.json();
        setResendMessage(errorData.detail || t("connexion.resend.error"));
        setResendStatus("error");
      }
    } catch (err) {
      console.error("Erreur lors du renvoi de l'email de vérification:", err);
      setResendMessage(t("connexion.resend.networkError"));
      setResendStatus("error");
    }
  };

  // Reutilise le meme endpoint que le renvoi d'email de verification ci-dessus
  // (reset-password-request) - le backend ne revele jamais si l'adresse existe, donc un simple
  // message generique convient ici aussi, sans exposer d'information sur les comptes existants.
  const handleForgotPassword = async () => {
    if (!email) {
      setForgotPasswordMessage(t("connexion.forgotPasswordFlow.emailRequired"));
      return;
    }
    setForgotPasswordMessage(t("connexion.forgotPasswordFlow.sending"));
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/reset-password-request/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await response.json();
      setForgotPasswordMessage(
        data.message || data.detail || t("connexion.forgotPasswordFlow.genericSuccess")
      );
    } catch (err) {
      console.error("Erreur lors de la demande de réinitialisation:", err);
      setForgotPasswordMessage(t("connexion.forgotPasswordFlow.networkError"));
    }
  };

  return (
    <>
      <div className="connexion-wrapper d-flex justify-content-center align-items-center min-vh-100 py-5">
        <div className="connexion-container">
          <div className="connexion-card p-4">
            {/* Logo/Icon */}
            <div className="text-center mb-4">
              <div className="connexion-icon mx-auto mb-3">
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M5 12H19M19 12L12 5M19 12L12 19"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
              <h2 className="connexion-title mb-2">{t("connexion.title")}</h2>
              <p className="connexion-subtitle">{t("connexion.subtitle")}</p>
            </div>

            {/* Formulaire */}
            <form onSubmit={handleSubmit}>
              {/* Affichage de l'erreur, si présente */}
              {error && (
                <div className="alert alert-danger mb-3" role="alert">
                  {error}
                  {showResendEmailButton && (
                    <button
                      type="button"
                      className="btn btn-link text-decoration-none mt-2 d-block mx-auto"
                      onClick={handleResendVerificationEmail}
                    >
                      {t("connexion.resend.button")}
                    </button>
                  )}
                  {resendMessage && (
                    <p
                      className="text-center mt-2"
                      style={{
                        fontSize: "0.9rem",
                        color:
                          resendStatus === "success"
                            ? "green"
                            : resendStatus === "error"
                            ? "red"
                            : undefined,
                      }}
                    >
                      {resendMessage}
                    </p>
                  )}
                </div>
              )}

              {/* Email */}
              <div className="mb-3">
                <div className="input-group connexion-input-group">
                  <span className="input-group-text connexion-input-icon">
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        d="M4 4H20C21.1 4 22 4.9 22 6V18C22 19.1 21.1 20 20 20H4C2.9 20 2 19.1 2 18V6C2 4.9 2.9 4 4 4Z"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      <polyline
                        points="22,6 12,13 2,6"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </span>
                  <input
                    type="email"
                    className="form-control connexion-input"
                    placeholder={t("connexion.placeholders.email")}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
              </div>

              {/* Mot de passe */}
              <div className="mb-3">
                <div className="input-group connexion-input-group">
                  <span className="input-group-text connexion-input-icon">
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <rect
                        x="3"
                        y="11"
                        width="18"
                        height="11"
                        rx="2"
                        ry="2"
                        stroke="currentColor"
                        strokeWidth="2"
                      />
                      <circle cx="12" cy="16" r="1" fill="currentColor" />
                      <path
                        d="M7 11V7A5 5 0 0 1 17 7V11"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </span>
                  <input
                    type={showPassword ? "text" : "password"}
                    className="form-control connexion-input"
                    placeholder={t("connexion.placeholders.password")}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                  <button
                    type="button"
                    className="btn connexion-password-toggle"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      {showPassword ? (
                        <path
                          d="M17.94 17.94A10.07 10.07 0 0 1 12 20C7 20 2.73 16.39 1 12A18.45 18.45 0 0 1 5.06 5.06L17.94 17.94ZM9.9 4.24A9.12 9.12 0 0 1 12 4C17 4 21.27 7.61 23 12A18.5 18.5 0 0 1 19.42 16.42L9.9 4.24ZM1 1L23 23M8.21 8.21A2 2 0 0 0 12 14A2 2 0 0 0 15.79 15.79"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      ) : (
                        <>
                          <path
                            d="M1 12S5 4 12 4S23 12 23 12S19 20 12 20S1 12 1 12Z"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                          <circle
                            cx="12"
                            cy="12"
                            r="3"
                            stroke="currentColor"
                            strokeWidth="2"
                          />
                        </>
                      )}
                    </svg>
                  </button>
                </div>
              </div>

              {/* Options */}
              <div className="d-flex justify-content-between align-items-center mb-4 me-1">
                <div className="form-check">
                  <input
                    className="form-check-input connexion-checkbox"
                    type="checkbox"
                    id="rememberMe"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                  />
                  <label
                    className="form-check-label connexion-checkbox-label"
                    htmlFor="rememberMe"
                  >
                    {t("connexion.rememberMe")}
                  </label>
                </div>
                <button
                  type="button"
                  className="connexion-forgot-link btn btn-link p-0"
                  onClick={handleForgotPassword}
                >
                  {t("connexion.forgotPassword")}
                </button>
              </div>
              {forgotPasswordMessage && (
                <p className="small text-center mt-2">{forgotPasswordMessage}</p>
              )}

              {/* Bouton de connexion */}
              <button
                type="submit"
                className="btn connexion-btn-primary w-100 mb-4"
              >
                {t("connexion.submit")}
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                  className="ms-2"
                >
                  <path
                    d="M5 12H19M19 12L12 5M19 12L12 19"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>

              {/* Séparateur */}
              <div className="connexion-divider mb-4">
                <span>{t("connexion.divider")}</span>
              </div>

              {/* Boutons sociaux */}
              <div className="row g-2 mb-4">
                <div className=" col-12">
                  <button
                    type="button"
                    className="btn connexion-btn-social w-100"
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                      className="me-2"
                    >
                      <path
                        d="M22.56 12.25C22.56 11.47 22.49 10.72 22.36 10H12V14.26H17.92C17.66 15.63 16.9 16.79 15.77 17.57V20.34H19.32C21.41 18.42 22.56 15.6 22.56 12.25Z"
                        fill="#4285F4"
                      />
                      <path
                        d="M12 23C15.24 23 17.95 21.92 19.32 20.34L15.77 17.57C14.77 18.22 13.48 18.63 12 18.63C8.87 18.63 6.22 16.68 5.32 13.95H1.64V16.83C3.01 19.55 7.27 23 12 23Z"
                        fill="#34A853"
                      />
                      <path
                        d="M5.32 13.95C5.1 13.3 4.98 12.61 4.98 11.89C4.98 11.17 5.1 10.48 5.32 9.83V6.95H1.64C0.89 8.44 0.5 10.13 0.5 11.89C0.5 13.65 0.89 15.34 1.64 16.83L5.32 13.95Z"
                        fill="#FBBC05"
                      />
                      <path
                        d="M12 5.38C13.62 5.38 15.06 5.94 16.21 7.02L19.36 3.87C17.95 2.54 15.24 1.5 12 1.5C7.27 1.5 3.01 4.95 1.64 7.67L5.32 10.55C6.22 7.82 8.87 5.38 12 5.38Z"
                        fill="#EA4335"
                      />
                    </svg>
                    {t("connexion.google")}
                  </button>
                </div>
              </div>

              {/* Lien d'inscription */}
              <div className="text-center">
                <p className="connexion-signup-text">
                  {t("connexion.noAccount")}
                  <Link
                    className="connexion-signup-link ms-1"
                    to="/Inscription"
                  >
                    {t("connexion.signupLink")}
                  </Link>
                </p>
              </div>

              {/* Note de sécurité */}
              <div className="connexion-security-note mt-4">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                  className="me-2"
                >
                  <path
                    d="M12 22S2 16 2 9C2 7 3 5 5 4C7 3 9 4 12 6C15 4 17 3 19 4C21 5 22 7 22 9C22 16 12 22 12 22Z"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                <small>{t("connexion.securityNote")}</small>
              </div>
            </form>
          </div>
        </div>
      </div>
    </>
  );
};

export default Connexion;
