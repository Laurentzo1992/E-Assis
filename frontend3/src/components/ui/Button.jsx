import React from 'react';

/**
 * @file Button.jsx
 * @description Composant de bouton réutilisable.
 * Fournit une interface uniforme pour les boutons avec des états de chargement.
 */

/**
 * Composant Button.
 * @param {Object} props - Les props du composant.
 * @param {string} [props.variant="primary"] - Variante de couleur Bootstrap (ex: "primary", "danger", "outline-secondary").
 * @param {string} [props.size=""] - Taille du bouton (ex: "sm", "lg").
 * @param {boolean} [props.loading=false] - Indique si le bouton est en état de chargement.
 * @param {string} [props.loadingText="Chargement..."] - Texte à afficher pendant le chargement.
 * @param {string} [props.className=""] - Classes CSS supplémentaires.
 * @param {boolean} [props.disabled=false] - Rend le bouton désactivé.
 * @param {string} [props.type="button"] - Type du bouton HTML (ex: "submit", "button").
 * @param {React.ReactNode} props.children - Le contenu du bouton.
 * @param {Function} [props.onClick] - Fonction de rappel à exécuter lors du clic.
 */
const Button = ({
  variant = "primary",
  size = "",
  loading = false,
  loadingText = "Chargement...",
  className = "",
  disabled = false,
  type = "button",
  children,
  onClick,
  ...rest // Pour passer d'autres attributs HTML (ex: aria-label)
}) => {
  const btnClasses = `btn btn-${variant} ${size ? `btn-${size}` : ''} ${className}`;

  return (
    <button
      type={type}
      className={btnClasses}
      onClick={onClick}
      disabled={disabled || loading} // Désactive si 'disabled' ou 'loading' est vrai
      {...rest}
    >
      {loading ? (
        <>
          <span
            className="spinner-border spinner-border-sm me-2"
            role="status"
            aria-hidden="true"
          ></span>
          {loadingText}
        </>
      ) : (
        children
      )}
    </button>
  );
};

export default Button;