import React, { useEffect, useRef } from "react";
import { Modal } from "bootstrap";

/**
 * Modal affichant les détails d'une publication sélectionnée.
 * - Sur petits écrans il utilise full-screen modal (Bootstrap class `modal-fullscreen-sm-down`).
 * - Sur grands écrans il reste centré et de taille `modal-lg`.
 */
const PublicationDetailModal = ({ show, onClose, publication }) => {
  const modalRef = useRef(null);
  const modalInstance = useRef(null);

  // Création de l'instance Bootstrap Modal
  useEffect(() => {
    if (modalRef.current) {
      modalInstance.current = new Modal(modalRef.current, { keyboard: true });
    }

    return () => {
      if (modalInstance.current) {
        try {
          modalInstance.current.dispose();
        } catch (e) {
          /* ignore */
        }
      }
    };
  }, []);

  // Affiche/masque le modal en fonction de la prop `show`
  useEffect(() => {
    if (!modalInstance.current) return;
    if (show) modalInstance.current.show();
    else modalInstance.current.hide();
  }, [show]);

  if (!publication) return null;

  return (
    <div
      className="modal fade"
      ref={modalRef}
      tabIndex={-1}
      id="publicationDetailModal"
    >
      <div className="modal-dialog modal-lg modal-dialog-centered modal-fullscreen-sm-down modal-dialog-scrollable">
        <div className="modal-content">
          <div className="modal-header">
            <h5 className="modal-title">Aperçu de la publication</h5>
            <button
              type="button"
              className="btn-close"
              aria-label="Fermer"
              onClick={onClose}
            ></button>
          </div>

          <div className="modal-body">
            <div className="container-fluid">
              <div className="row">
                <div className="col-12 col-md-8 mb-3 mb-md-0">
                  <h6 className="fw-bold">{publication.title}</h6>
                  <p className="text-muted small mb-2">
                    <strong>Date de publication :</strong>{" "}
                    {publication.date_publication
                      ? new Date(
                          publication.date_publication
                        ).toLocaleDateString("fr-FR")
                      : "N/A"}
                  </p>
                  <p className="text-muted small mb-2">
                    <strong>Numéro de revue :</strong>{" "}
                    {publication.numero_revue || "N/A"}
                  </p>
                  <p className="text-muted small mb-2">
                    <strong>Source :</strong>{" "}
                    {publication.url ? (
                      <a
                        href={publication.url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {publication.url}
                      </a>
                    ) : (
                      "N/A"
                    )}
                  </p>
                </div>

                <div className="col-12 col-md-4">
                  <div className="p-2 border rounded bg-light h-100 d-flex flex-column">
                    {publication.excerpt ? (
                      <>
                        <h6 className="mb-2">Extrait</h6>
                        <p className="small text-muted">
                          {publication.excerpt}
                        </p>
                      </>
                    ) : (
                      <p className="small text-muted">
                        Aucun extrait disponible.
                      </p>
                    )}

                    <div className="mt-auto">
                      {publication.url && (
                        <a
                          className="btn btn-sm btn-primary w-100"
                          href={publication.url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          Voir la source
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PublicationDetailModal;
