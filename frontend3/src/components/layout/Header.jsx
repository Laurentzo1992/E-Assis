import React from 'react';

/**
 * @file Header.jsx
 * @description Composant d'en-tête pour la version mobile du tableau de bord.
 * Affiche le titre de l'application et un bouton pour ouvrir la barre latérale.
 */

/**
 * Composant Header.
 * @param {Object} props - Les props du composant.
 * @param {Function} props.onMenuClick - Fonction de rappel à exécuter lorsque le bouton de menu est cliqué.
 */
const Header = ({ onMenuClick }) => {
  return (
    <div className="mobile-header d-md-none">
      <button className="btn-menu" onClick={onMenuClick}>
        {/* Icône de menu (hamburger) */}
        <svg width="24" height="24" fill="currentColor" viewBox="0 0 16 16">
          <path
            fillRule="evenodd"
            d="M2.5 12a.5.5 0 0 1 .5-.5h10a.5.5 0 0 1 0 1H3a.5.5 0 0 1-.5-.5zm0-4a.5.5 0 0 1 .5-.5h10a.5.5 0 0 1 0 1H3a.5.5 0 0 1-.5-.5zm0-4a.5.5 0 0 1 .5-.5h10a.5.5 0 0 1 0 1H3a.5.5 0 0 1-.5-.5z"
          />
        </svg>
      </button>
      <h5 className="m-0">VeilleMarches Pro</h5>
    </div>
  );
};

export default Header;