import React, { useState } from "react";
import { User } from "lucide-react";
import { useNavigate, Link } from "react-router-dom";
import "./style.css"; // Ton fichier CSS personnalisé

// On reproduit ici la structure utilisée dans `Connexion.jsx` pour être cohérent
// avec le design : input-group avec icône dans span.input-group-text et classes
// partagées (connexion-input-group / connexion-input / connexion-input-icon)
const InputField = ({
  svgIcon,
  type = "text",
  placeholder,
  value,
  onChange,
  error,
  id,
  required = false,
}) => (
  <div className="mb-3">
    <div className="input-group connexion-input-group">
      <span className="input-group-text connexion-input-icon" aria-hidden>
        {svgIcon}
      </span>
      <input
        type={type}
        className={`form-control connexion-input ${error ? "is-invalid" : ""}`}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        id={id}
        name={id}
        autoComplete="off"
        required={required}
      />
    </div>
    {error && <div className="invalid-feedback d-block">{error}</div>}
  </div>
);

export default function InscriptionBootstrap() {
  const [formData, setFormData] = useState({
    nomRepresentant: "",
    prenomRepresentant: "",
    email: "",
    password: "",
    password2: "",
  });

  const [errors, setErrors] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showPassword2, setShowPassword2] = useState(false);
  // const [successMessage, setSuccessMessage] = useState(""); // Supprimé
  const navigate = useNavigate();

  // (Google Sign-In removed) : inscription via Google désactivée — champ email entièrement éditable

  const handleChange = (field) => (e) => {
    setFormData((prev) => ({ ...prev, [field]: e.target.value }));
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: "" }));
    }
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.nomRepresentant.trim())
      newErrors.nomRepresentant = "Le nom du représentant est requis";
    if (!formData.prenomRepresentant.trim())
      newErrors.prenomRepresentant = "Le prénom du représentant est requis";

    if (!formData.email.trim()) {
      newErrors.email = "L'email est requis";
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = "Format d'email invalide";
    }

    if (!formData.password) {
      newErrors.password = "Le mot de passe est requis";
    }

    if (!formData.password2) {
      newErrors.password2 = "La confirmation du mot de passe est requise";
    } else if (formData.password !== formData.password2) {
      newErrors.password2 = "Les mots de passe ne correspondent pas";
    }

    return newErrors;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrors({}); // Réinitialise les erreurs précédentes
    // setSuccessMessage(""); // Supprimé

    const newErrors = validateForm();
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch("http://127.0.0.1:8000/api/auth/register/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: formData.email,
          repnom: formData.nomRepresentant,
          repprenom: formData.prenomRepresentant,
          password: formData.password,
          password2: formData.password2,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        // Gérer les erreurs spécifiques de l'API
        const apiErrors = {};
        for (const key in data) {
          apiErrors[key] = Array.isArray(data[key]) ? data[key][0] : data[key];
        }
        setErrors(apiErrors);
        // Afficher une alerte générique pour les erreurs non liées à un champ spécifique
        if (data.detail) {
          alert(`Erreur d'inscription: ${data.detail}`);
        } else if (Object.keys(apiErrors).length === 0) {
          alert("Une erreur inattendue est survenue lors de l'inscription.");
        }
      } else {
        navigate("/email-verification-sent");
      }
    } catch (error) {
      console.error("Erreur réseau ou serveur:", error);
      alert("Erreur réseau ou serveur. Veuillez réessayer plus tard.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <link
        href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/css/bootstrap.min.css"
        rel="stylesheet"
      />

      <div className="d-flex align-items-center justify-content-center p-4 custom-bg">
        <div className="container">
          <div className="row justify-content-center">
            <div className="col-12 col-md-11 col-lg-10 col-xl-9">
              <div className="custom-card p-4 p-sm-5">
                <div className="text-center mb-4">
                  <h2 className="h2 fw-bold text-primary-custom mb-2">
                    Inscription Entreprise
                  </h2>
                  <p className="text-primary-custom opacity-75">
                    Rejoignez notre plateforme dès aujourd'hui
                  </p>
                </div>

                <form onSubmit={handleSubmit}>
                  {/* Le message de succès est maintenant une alerte simple */}
                  {/* {successMessage && (
                    <div className="alert alert-success mb-3" role="alert">
                      {successMessage}
                    </div>
                  )} */}
                  {/* Les messages d'erreur spécifiques aux champs sont gérés par InputField */}

                  <div className="row">
                    <div className="col-12 col-sm-6">
                      <InputField
                        svgIcon={<User size={16} />}
                        placeholder="Nom du représentant"
                        value={formData.nomRepresentant}
                        onChange={handleChange("nomRepresentant")}
                        error={errors.nomRepresentant}
                        id="nomRepresentant"
                        required
                      />
                    </div>
                    <div className="col-12 col-sm-6">
                      <InputField
                        svgIcon={<User size={16} />}
                        placeholder="Prénom du représentant"
                        value={formData.prenomRepresentant}
                        onChange={handleChange("prenomRepresentant")}
                        error={errors.prenomRepresentant}
                        id="prenomRepresentant"
                        required
                      />
                    </div>
                  </div>

                  <InputField
                    svgIcon={
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
                    }
                    type="email"
                    placeholder="Adresse email"
                    value={formData.email}
                    onChange={handleChange("email")}
                    error={errors.email}
                    id="email"
                    required
                  />

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
                        className={`form-control connexion-input ${
                          errors.password ? "is-invalid" : ""
                        }`}
                        placeholder="Mot de passe"
                        value={formData.password}
                        onChange={handleChange("password")}
                        id="password"
                      />
                      <button
                        type="button"
                        className="btn connexion-password-toggle"
                        onClick={() => setShowPassword(!showPassword)}
                        aria-label={
                          showPassword
                            ? "Masquer le mot de passe"
                            : "Afficher le mot de passe"
                        }
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
                    {errors.password && (
                      <div className="invalid-feedback d-block">
                        {errors.password}
                      </div>
                    )}
                  </div>

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
                        type={showPassword2 ? "text" : "password"}
                        className={`form-control connexion-input ${
                          errors.password2 ? "is-invalid" : ""
                        }`}
                        placeholder="Confirmer le mot de passe"
                        value={formData.password2}
                        onChange={handleChange("password2")}
                        id="password2"
                      />
                      <button
                        type="button"
                        className="btn connexion-password-toggle"
                        onClick={() => setShowPassword2(!showPassword2)}
                        aria-label={
                          showPassword2
                            ? "Masquer le mot de passe"
                            : "Afficher le mot de passe"
                        }
                      >
                        <svg
                          width="16"
                          height="16"
                          viewBox="0 0 24 24"
                          fill="none"
                          xmlns="http://www.w3.org/2000/svg"
                        >
                          {showPassword2 ? (
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
                    {errors.password2 && (
                      <div className="invalid-feedback d-block">
                        {errors.password2}
                      </div>
                    )}
                  </div>

                  <div className="pt-3">
                    <button
                      type="submit"
                      className="custom-btn text-white w-100"
                      disabled={isLoading}
                    >
                      {isLoading
                        ? "Inscription en cours..."
                        : "Créer le compte entreprise"}
                    </button>
                  </div>
                </form>
                {/* Google sign-in removed */}

                <div className="text-center mt-4">
                  <p className="small text-primary-custom">
                    Déjà un compte ?{" "}
                    <Link
                      to="/connexion"
                      className="text-orange-custom text-decoration-none fw-medium"
                    >
                      Se connecter
                    </Link>
                  </p>
                </div>

                {/* Terms and privacy text removed as requested */}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
