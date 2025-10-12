import React from 'react';
import PublicationTableRow from './PublicationTableRow';
import PublicationCard from './PublicationCard';

/**
 * @file PublicationList.jsx
 * @description Affiche une liste de publications.
 * Gère l'affichage responsive en utilisant un tableau pour les grands écrans
 * et des cartes pour les petits écrans.
 */
const PublicationList = ({ publications, onViewClick }) => {
  if (publications.length === 0) {
    return <p className="text-center text-muted p-4">Aucune publication ne correspond à vos critères de recherche.</p>;
  }

  return (
    <>
      {/* --- Version Tableau (Desktop) --- */}
      <div className="table-responsive d-none d-lg-block">
        <table className="table table-hover align-middle">
          <thead>
            <tr>
              <th>Date</th>
              <th>Titre</th>
              <th>N° Revue</th>
              <th className="text-end">Actions</th>
            </tr>
          </thead>
          <tbody>
            {publications.map((pub) => (
              <PublicationTableRow
                key={pub.id}
                publication={pub}
                onViewClick={onViewClick}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* --- Version Cartes (Mobile/Tablette) --- */}
      <div className="d-lg-none">
        {publications.map((pub) => (
          <PublicationCard
            key={pub.id}
            publication={pub}
            onViewClick={onViewClick}
          />
        ))}
      </div>
    </>
  );
};

export default PublicationList;