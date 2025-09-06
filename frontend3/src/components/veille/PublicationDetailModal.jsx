import React, { useEffect, useRef } from 'react';
import { Modal } from 'bootstrap';

/**
 * @file PublicationDetailModal.jsx
 * @description Modal affichant les détails d'une publication sélectionnée.
 * Gère sa propre instance de modal Bootstrap.
 */
const PublicationDetailModal = ({ show, onClose, publication }) => {
  const modalRef = useRef();
  const modalInstance = useRef(null);

  // Gère la création et la destruction de l'instance du modal Bootstrap
  useEffect(() => {
    if (modalRef.current) {
      modalInstance.current = new Modal(modalRef.current, {
        keyboard: true
      });

      // Nettoyage pour éviter les problèmes de re-création
      return () => {
        if (modalInstance.current) {
          // modalInstance.current.dispose(); //
        }
      };
    }
  }, []);

  // Gère l'affichage/masquage du modal en fonction de la prop `show`
  useEffect(() => {
    if (modalInstance.current) {
      if (show) {
        modalInstance.current.show();
      } else {
        modalInstance.current.hide();
      }
    }
  }, [show]);

  if (!publication) {
    return null; // Ne rien rendre si aucune publication n'est sélectionnée
  }

  return (
    <div className="modal fade" ref={modalRef} tabIndex="-1" id="publicationDetailModal">
      <div className="modal-dialog modal-lg">
        <div className="modal-content">
          <div className="modal-header">
            <h5 className="modal-title">Aperçu de la publication</h5>
            <button type="button" className="btn-close" onClick={onClose}></button>
          </div>
          <div className="modal-body">
            <h6>{publication.title}</h6>
            <p className="text-muted mb-1">
              <strong>Date de publication :</strong> {new Date(publication.date_publication).toLocaleDateString('fr-FR')}
            </p>
            <p className="text-muted mb-1">
              <strong>Numéro de revue :</strong> {publication.numero_revue || 'N/A'}
            </p>
            <p className="text-muted">
              <strong>Source :</strong> <a href={publication.url} target="_blank" rel="noopener noreferrer">{publication.url}</a>
            </p>
          </div>
          
        </div>
      </div>
    </div>
  );
};

export default PublicationDetailModal;