import React from 'react';

/**
 * @file Spinner.jsx
 * @description Composant simple d'indicateur de chargement.
 * Utilise Bootstrap's spinner.
 */

/**
 * Composant Spinner.
 * @param {Object} props - Les props du composant.
 * @param {string} [props.message="Chargement..."] - Message à afficher sous le spinner.
 * @param {string} [props.size=""] - Taille du spinner ("sm" pour petit).
 * @param {string} [props.variant="primary"] - Couleur du spinner (ex: "primary", "secondary", etc.).
 */
const Spinner = ({ message = "Chargement...", size = "", variant = "primary" }) => {
  return (
    <div className="d-flex flex-column align-items-center justify-content-center">
      <div 
        className={`spinner-border text-${variant} ${size ? `spinner-border-${size}` : ''}`} 
        role="status"
      >
        <span className="visually-hidden">{message}</span>
      </div>
      {message && <p className="mt-2 text-muted">{message}</p>}
    </div>
  );
};

export default Spinner;