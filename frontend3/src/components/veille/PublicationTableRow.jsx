import React from 'react';
import Button from '../ui/Button'; // On conserve notre composant Bouton

/**
 * @file PublicationTableRow.jsx
 * @description Affiche une seule publication sous forme de ligne de tableau (<tr>).
 */
const PublicationTableRow = ({ publication }) => {
  // On remplace l'appel à onViewClick par une fonction qui ouvre l'URL
  const handleViewClick = () => {
    // Ouvre l'URL de la publication dans un nouvel onglet de manière sécurisée
    window.open(publication.url, '_blank', 'noopener,noreferrer');
  };

  return (
    <tr>
      <td>{new Date(publication.date_publication).toLocaleDateString('fr-FR')}</td>
      <td className="fw-bold">{publication.title}</td>
      <td>{publication.numero_revue || 'N/A'}</td>
      <td className="text-end">
        <Button
          variant="outline-primary"
          size="sm"
          onClick={handleViewClick} // On appelle notre nouvelle fonction
        >
          Voir
        </Button>
      </td>
    </tr>
  );
};

export default PublicationTableRow;