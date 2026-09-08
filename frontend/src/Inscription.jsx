import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { User, Mail, Lock } from "lucide-react";
import { useNavigate } from "react-router-dom";
import Navbar from "./components/Navbar";
import { API_BASE_URL } from "./config";
import "./style.css"; // Ton fichier CSS personnalisé

// Composant pour les champs de saisie avec icône et gestion d'erreur
const InputField = ({
  icon: Icon,
  type = "text",
  placeholder,
  value,
  onChange,
  error,
  id,
  readOnly = false, // Prop pour rendre le champ en lecture seule
}) => (
  <div className="mb-3 position-relative">
    <div className="input-icon">
      <Icon size={20} />
    </div>
    <input
      type={type}
      className={`form-control custom-input ${error ? "is-invalid" : ""}`}
      placeholder={placeholder}
      value={value}
      onChange={onChange}
      id={id}
      style={{ paddingLeft: "3rem", height: "3.5rem" }}
      readOnly={readOnly} // Applique la prop readOnly
    />
    {error && <div className="invalid-feedback">{error}</div>}
  </div>
);

// Le widget Google Identity Services accepte un code locale different du notre pour "mos" (le
// Moore n'est pas supporte par Google) - repli sur le francais dans ce cas.
const GOOGLE_LOCALES = { fr: "fr", en: "en", mos: "fr" };

export default function InscriptionBootstrap() {
  const { t, i18n } = useTranslation();
  const [formData, setFormData] = useState({
    nomRepresentant: "",
    prenomRepresentant: "",
    email: "",
    password: "",
    password2: "",
  });

  const [errors, setErrors] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  // const [successMessage, setSuccessMessage] = useState(""); // Supprimé
  const navigate = useNavigate();

  // Effet pour charger le script Google Identity Services et initialiser le bouton
  useEffect(() => {
    // Charger le script Google Identity Services
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = () => {
      // Initialiser Google Identity Services après le chargement du script
      if (window.google) {
        window.google.accounts.id.initialize({
          client_id: "YOUR_GOOGLE_CLIENT_ID", // PLACEHOLDER pour l'ID client Google
          callback: handleGoogleCredentialResponse, // Fonction de rappel pour gérer la réponse
          auto_select: false, // Ne pas sélectionner automatiquement un compte
          cancel_on_tap_outside: true,
        });

        // Rendre le bouton Google Sign-In
        window.google.accounts.id.renderButton(
          document.getElementById("google-sign-in-button"),
          {
            theme: "outline",
            size: "large",
            text: "signup_with", // Texte du bouton (ex: "Sign up with Google")
            width: "100%", // Adapter la largeur
            locale: GOOGLE_LOCALES[i18n.language] || "fr", // Langue du bouton
          }
        );
      }
    };
    document.body.appendChild(script);

    // Nettoyage lors du démontage du composant
    return () => {
      document.body.removeChild(script);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [i18n.language]); // Recharge le bouton Google si la langue change

  // Fonction de rappel pour gérer la réponse de Google Sign-In
  const handleGoogleCredentialResponse = async (response) => {
    // response.credential contient l'ID token JWT
    if (response.credential) {
      try {
        // Décoder le token pour obtenir les informations de l'utilisateur
        const decodedToken = JSON.parse(
          atob(response.credential.split(".")[1])
        );

        setFormData((prev) => ({
          ...prev,
          email: decodedToken.email || "",
          prenomRepresentant: decodedToken.given_name || "",
          nomRepresentant: decodedToken.family_name || "",
          // Ne pas pré-remplir les mots de passe, l'utilisateur devra les définir
          password: "",
          password2: "",
        }));
        setErrors({}); // Effacer les erreurs précédentes si le pré-remplissage réussit
        // setSuccessMessage("Champs pré-remplis avec votre compte Google. Veuillez définir un mot de passe pour finaliser l'inscription."); // Supprimé
      } catch (error) {
        console.error("Erreur lors du décodage du token Google:", error);
        alert(t("inscription.alerts.googleError"));
      }
    }
  };

  const handleChange = (field) => (e) => {
    setFormData((prev) => ({ ...prev, [field]: e.target.value }));
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: "" }));
    }
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.nomRepresentant.trim())
      newErrors.nomRepresentant = t("inscription.errors.nom");
    if (!formData.prenomRepresentant.trim())
      newErrors.prenomRepresentant = t("inscription.errors.prenom");

    if (!formData.email.trim()) {
      newErrors.email = t("inscription.errors.emailRequired");
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = t("inscription.errors.emailInvalid");
    }

    if (!formData.password) {
      newErrors.password = t("inscription.errors.passwordRequired");
    }

    if (!formData.password2) {
      newErrors.password2 = t("inscription.errors.password2Required");
    } else if (formData.password !== formData.password2) {
      newErrors.password2 = t("inscription.errors.passwordMismatch");
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
      const response = await fetch(`${API_BASE_URL}/api/auth/register/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: formData.email,
          first_name: formData.prenomRepresentant, // Assurez-vous que le backend attend 'first_name'
          last_name: formData.nomRepresentant, // Assurez-vous que le backend attend 'last_name'
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
          alert(t("inscription.alerts.registrationError", { detail: data.detail }));
        } else if (Object.keys(apiErrors).length === 0) {
          alert(t("inscription.alerts.unexpectedError"));
        }
      } else {
        navigate("/email-verification-sent");
      }
    } catch (error) {
      console.error("Erreur réseau ou serveur:", error);
      alert(t("inscription.alerts.networkError"));
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

      <Navbar />

      <div className="d-flex align-items-center justify-content-center p-4 custom-bg">
        <div className="container">
          <div className="row justify-content-center">
            <div className="col-12 col-md-11 col-lg-10 col-xl-9">
              <div className="custom-card p-4 p-sm-5">
                <div className="text-center mb-4">
                  <h2 className="h2 fw-bold text-primary-custom mb-2">
                    {t("inscription.title")}
                  </h2>
                  <p className="text-primary-custom opacity-75">
                    {t("inscription.subtitle")}
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
                        icon={User}
                        placeholder={t("inscription.placeholders.nom")}
                        value={formData.nomRepresentant}
                        onChange={handleChange("nomRepresentant")}
                        error={errors.nomRepresentant}
                        id="nomRepresentant"
                      />
                    </div>
                    <div className="col-12 col-sm-6">
                      <InputField
                        icon={User}
                        placeholder={t("inscription.placeholders.prenom")}
                        value={formData.prenomRepresentant}
                        onChange={handleChange("prenomRepresentant")}
                        error={errors.prenomRepresentant}
                        id="prenomRepresentant"
                      />
                    </div>
                  </div>

                  <InputField
                    icon={Mail}
                    type="email"
                    placeholder={t("inscription.placeholders.email")}
                    value={formData.email}
                    onChange={handleChange("email")}
                    error={errors.email}
                    id="email"
                    // readOnly={!!formData.email && successMessage.includes("Champs pré-remplis")} // Logique de lecture seule simplifiée
                    readOnly={
                      !!formData.email &&
                      !errors.email &&
                      formData.prenomRepresentant &&
                      formData.nomRepresentant
                    } // Rend l'email en lecture seule si pré-rempli et valide
                  />

                  <InputField
                    icon={Lock}
                    type="password"
                    placeholder={t("inscription.placeholders.password")}
                    value={formData.password}
                    onChange={handleChange("password")}
                    error={errors.password}
                    id="password"
                  />

                  <InputField
                    icon={Lock}
                    type="password"
                    placeholder={t("inscription.placeholders.password2")}
                    value={formData.password2}
                    onChange={handleChange("password2")}
                    error={errors.password2}
                    id="password2"
                  />

                  <div className="pt-3">
                    <button
                      type="submit"
                      className="custom-btn text-white w-100"
                      disabled={isLoading}
                    >
                      {isLoading
                        ? t("inscription.submit.loading")
                        : t("inscription.submit.default")}
                    </button>
                  </div>
                </form>
                {/* Séparateur */}
                <div className="connexion-divider mb-4">
                  <span>{t("inscription.divider")}</span>
                </div>

                <div className="row g-2 mb-4">
                  <div className=" col-12">
                    {/* Le bouton Google sera rendu ici par Google Identity Services */}
                    <div id="google-sign-in-button" className="w-100"></div>
                  </div>
                </div>

                <div className="text-center mt-4">
                  <p className="small text-primary-custom">
                    {t("inscription.alreadyAccount")}{" "}
                    <a
                      href="/connexion"
                      className="text-orange-custom text-decoration-none fw-medium"
                    >
                      {t("inscription.login")}
                    </a>
                  </p>
                </div>

                <div className="text-center mt-3">
                  <p className="small text-primary-custom opacity-75">
                    {t("inscription.terms")}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
