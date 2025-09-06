import React from 'react';
import { Link } from 'react-router-dom';

/**
 * @file NotificationItem.jsx
 * @description
 * La carte entière est un lien qui, au clic, marque la notification comme lue
 * et navigue vers la page de détail du marché.
 */

const formatDate = (dateString) => {
  if (!dateString) return "Non spécifié";
  try {
    return new Date(dateString).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch (e) {
    return "Date invalide";
  }
};

const ResultBanner = ({ resultat }) => {
  if (!resultat) return null;
  const isWinner = resultat.statut === 'Retenu';
  const bannerClass = isWinner ? 'bg-success-subtle text-success-emphasis' : 'bg-warning-subtle text-warning-emphasis';
  const icon = isWinner ? '🏆' : '⚠️';
  return (
    <div className={`p-2 rounded mb-3 ${bannerClass}`} style={{ border: `1px solid ${isWinner ? 'var(--bs-success-border-subtle)' : 'var(--bs-warning-border-subtle)'}`}}>
      <h6 className="mb-1 fw-bold">{icon} Votre Résultat : {resultat.statut}</h6>
      {resultat.rang && <p className="mb-0 small"><strong>Rang :</strong> {resultat.rang}</p>}
      {resultat.montant_propose && <p className="mb-0 small"><strong>Montant soumis :</strong> {parseFloat(resultat.montant_propose).toLocaleString('fr-FR')} FCFA</p>}
      {resultat.motif && <p className="mb-0 small"><strong>Motif :</strong> {resultat.motif}</p>}
    </div>
  );
};

const NotificationItem = ({ notification, onNotificationClick }) => {
  const { lu, marche_objet, created_at, type_notification, marche_date_depot, resultat_pour_entreprise, marche } = notification;

  const isOpportunity = type_notification === 'DOMAINE';

  if (!marche) {
    return (
      <div className="card h-100 border-0 shadow-sm">
        <div className="card-body alert alert-danger small mb-0">
          Notification invalide : ID du marché manquant.
        </div>
      </div>
    );
  }

  const handleClick = () => {
    onNotificationClick(notification);
  };

  return (
    <div
      onClick={handleClick}
      className="card h-100 position-relative border-0 shadow-sm notification-card-clickable"
      style={{
        borderRadius: '15px',
        transition: 'transform 0.2s, box-shadow 0.2s',
        cursor: 'pointer',
        backgroundColor: lu ? 'white' : '#f0f8ff'
      }}
      onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-2px)'}
      onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0)'}
    >
      {/* Indicateur Non lu */}
      {!lu && (
        <span
          className="position-absolute top-0 start-0 translate-middle p-2 bg-primary border border-light rounded-circle"
          style={{ zIndex: 2 }}
        >
          <span className="visually-hidden">Non lue</span>
        </span>
      )}

      <div className="card-body d-flex flex-column p-3">
        {/* Résultat */}
        {type_notification === 'ENTREPRISE_SPECIFIQUE' && <ResultBanner resultat={resultat_pour_entreprise} />}

        {/* Badge avec icône */}
        <div className="mb-2 d-flex align-items-center gap-2">
          <span
            className={`badge fw-semibold ${isOpportunity ? 'bg-primary text-white' : 'bg-info text-dark'}`}
            style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem', borderRadius: '8px' }}
          >
            {isOpportunity ? '💼 Nouvelle Opportunité' : '📄 Résultat de Candidature'}
          </span>
        </div>

        {/* Titre de la notification */}
        <h5 className="fw-bold mb-2" style={{ fontSize: '1rem', lineHeight: '1.2rem' }}>
          {marche_objet || "Objet non spécifié"}
        </h5>

        {/* Date limite pour opportunité */}
        {isOpportunity && marche_date_depot && (
          <div
            className="alert p-2 small mb-2"
            style={{ borderRadius: '10px', fontSize: '0.8rem' }}
          >
            ⏰ Date limite : {formatDate(marche_date_depot)}
          </div>
        )}

        {/* Date de réception */}
        <p className="text-muted small mt-auto mb-1" style={{ fontSize: '0.75rem' }}>
          Reçu le : {formatDate(created_at)}
        </p>

        {/* Call-to-action visuel */}
        <div className="text-end">
          <span className="text-primary fw-bold small" style={{ fontSize: '0.8rem' }}>
            Voir les détails →
          </span>
        </div>
      </div>
    </div>
  );
};


export default NotificationItem;