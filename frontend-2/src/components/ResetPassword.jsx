import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import "./DemandeResetPassword.css";

export default function ResetPassword() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    new_password: "",
    confirm_password: "",
  });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleChange = (field) => (e) =>
    setFormData({ ...formData, [field]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage("");
    setError("");
    setIsLoading(true);

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/api/auth/reset-password/${token}/`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(formData),
        }
      );
      const data = await response.json();
      if (!response.ok)
        throw new Error(data.error || "Erreur lors de la réinitialisation.");

      setMessage(
        "Mot de passe réinitialisé avec succès ! Vous allez être redirigé."
      );
      setTimeout(() => navigate("/connexion"), 3000); // Temps allongé pour la lecture
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const closeModal = () => {
    setError("");
    // Pas de fermeture pour le message de succès car on redirige
  };

  return (
    <div className="auth-container">
      <div className="auth-form-wrapper">
        <div className="auth-form-container">
          <h2 className="auth-title">Nouveau mot de passe</h2>
          <p className="auth-subtitle">
            Veuillez définir votre nouveau mot de passe.
          </p>
          <form onSubmit={handleSubmit}>
            <div className="auth-input-group">
              <input
                type="password"
                placeholder="Nouveau mot de passe"
                value={formData.new_password}
                onChange={handleChange("new_password")}
                required
              />
            </div>
            <div className="auth-input-group">
              <input
                type="password"
                placeholder="Confirmer le mot de passe"
                value={formData.confirm_password}
                onChange={handleChange("confirm_password")}
                required
              />
            </div>
            <button className="auth-button" type="submit" disabled={isLoading}>
              {isLoading ? "Réinitialisation..." : "Réinitialiser"}
            </button>
          </form>
        </div>
      </div>
      {(message || error) && (
        <div className="auth-modal-overlay">
          <div className={`auth-modal ${error ? "error" : "success"}`}>
            <h3>{error ? "Erreur" : "Succès"}</h3>
            <p>{message || error}</p>
            {error && <button onClick={closeModal}>Fermer</button>}
          </div>
        </div>
      )}
    </div>
  );
}
