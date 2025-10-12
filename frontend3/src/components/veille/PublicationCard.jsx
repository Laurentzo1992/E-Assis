import React from "react";
import Button from "../ui/Button";

/**
 * @file PublicationCard.jsx
 * @description Affiche une seule publication sous forme de carte pour les vues mobiles.
 */
const PublicationCard = ({ publication, onViewClick }) => {
  return (
    <div className="card shadow-sm mb-3">
      <div className="card-body">
        <h6 className="card-title">{publication.title}</h6>
        <div className="card-text text-muted">
          <p className="mb-1">
            <strong>Date :</strong>{" "}
            {new Date(publication.date_publication).toLocaleDateString("fr-FR")}
          </p>
          <p className="mb-2">
            <strong>N° Revue :</strong> {publication.numero_revue || "N/A"}
          </p>
        </div>
        <Button
          variant="outline-primary"
          size="sm"
          className="w-100"
          onClick={() => {
            if (publication.url) {
              // Ouvre le PDF / source dans un nouvel onglet (comportement desktop)
              window.open(publication.url, "_blank", "noopener,noreferrer");
            } else {
              // Fallback : afficher le modal de détail
              onViewClick(publication);
            }
          }}
        >
          Voir les détails
        </Button>
      </div>
    </div>
  );
};

export default PublicationCard;
