import React, { useState } from "react";
import "./DemandeResetPassword.css";

export default function DemandeResetPassword() {
  const [formData, setFormData] = useState({ email: "", repnom: "", repprenom: "" });
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
      const response = await fetch("http://localhost:8000/api/auth/request-reset-password/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });

      const data = await response.json();

      if (!response.ok) {
        let errorMessage = "Erreur lors de la demande.";
        if (data.error) {
          if (typeof data.error === "string") {
            errorMessage = data.error;
          } else if (typeof data.error === "object") {
            errorMessage = Object.values(data.error).flat().join(" | ");
          }
        }
        throw new Error(errorMessage);
      }
      
      setMessage(data.message || "Un email a été envoyé pour réinitialiser le mot de passe.");

    } catch (err) {
      setError(err.message);
    } finally {
        setIsLoading(false);
    }
  };

  const closeModal = () => {
    setMessage("");
    setError("");
  };

  return (
    <div className="auth-container">
      <div className="auth-form-wrapper">
        <div className="auth-form-container">
          <h2 className="auth-title">Réinitialisation du mot de passe</h2>
          <p className="auth-subtitle">
            Entrez vos informations pour recevoir un lien de réinitialisation.
          </p>
          <form onSubmit={handleSubmit}>
            <div className="auth-input-group">
              <input
                type="text"
                placeholder="Nom"
                value={formData.repnom}
                onChange={handleChange("repnom")}
                required
              />
            </div>
            <div className="auth-input-group">
              <input
                type="text"
                placeholder="Prénom"
                value={formData.repprenom}
                onChange={handleChange("repprenom")}
                required
              />
            </div>
            <div className="auth-input-group">
              <input
                type="email"
                placeholder="Email"
                value={formData.email}
                onChange={handleChange("email")}
                required
              />
            </div>
            <button className="auth-button" type="submit" disabled={isLoading}>
              {isLoading ? "Envoi..." : "Envoyer"}
            </button>
          </form>
        </div>
      </div>

      {(message || error) && (
        <div className="auth-modal-overlay">
          <div className={`auth-modal ${error ? 'error' : 'success'}`}>
            <h3>{error ? "Erreur" : "Succès"}</h3>
            <p>{message || error}</p>
            <button onClick={closeModal}>Fermer</button>
          </div>
        </div>
      )}
    </div>
  );
}