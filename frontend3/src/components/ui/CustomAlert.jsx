import React, { useState, useEffect, useRef } from "react";
import { Modal } from "bootstrap";

const CustomAlert = ({ show, message, type = "info", onClose }) => {
  const modalRef = useRef(null);
  // On utilise useState pour que React suive l'état de l'instance de la modale
  const [modalInstance, setModalInstance] = useState(null);
  // Effet 1: Gère UNIQUEMENT la création et la destruction de l'instance.
  // S'exécute une seule fois au montage et nettoie au démontage.
  useEffect(() => {
    if (modalRef.current) {
      const bsModal = new Modal(modalRef.current, {
        keyboard: true,
        backdrop: "static", 
      });
      setModalInstance(bsModal);

      // Fonction de nettoyage : essentielle pour éviter les fuites de mémoire.
      return () => {
        bsModal.dispose();
      };
    }
  }, []); // Le tableau vide garantit une exécution unique.

  // Effet 2: Gère l'affichage/masquage et les événements.
  // S'exécute lorsque l'instance est prête ou que la prop `show` change.
  useEffect(() => {
    if (!modalInstance) return;

    const modalElement = modalRef.current;
    
    // Notifie le parent que la modale est complètement fermée.
    const handleHidden = () => {
      if (onClose) onClose();
    };

    modalElement.addEventListener("hidden.bs.modal", handleHidden);

    // Synchronise l'état visible de la modale avec la prop `show`
    if (show) {
      modalInstance.show();
    } else {
      modalInstance.hide();
    }

    // Nettoie l'écouteur d'événement pour ce rendu spécifique.
    return () => {
      if (modalElement) {
        modalElement.removeEventListener("hidden.bs.modal", handleHidden);
      }
    };
  }, [show, modalInstance, onClose]);

  // Gère le clic sur les boutons de fermeture.
  // On appelle directement onClose pour que le parent mette à jour l'état `show`.
  const handleClose = () => {
    if (onClose) {
      onClose(); // Le changement de `show` à `false` déclenchera .hide() dans l'effet ci-dessus.
    }
  };

  // Logique de style
  const headerClass = { /* ... */ }[type] || "bg-secondary text-white";
  const buttonClass = { /* ... */ }[type] || "btn-secondary";
  const title = { /* ... */ }[type] || "Notification";

  // On retourne null si on ne doit pas afficher, pour que les effets se nettoient correctement
  if (!show) {
    return null;
  }

  return (
    <div
      className="modal fade"
      ref={modalRef}
      tabIndex="-1"
      aria-labelledby="customAlertModalLabel"
      aria-hidden="true"
    >
      <div className="modal-dialog modal-sm modal-dialog-centered">
        <div className="modal-content">
          <div className={`modal-header ${headerClass}`}>
            <h5 className="modal-title" id="customAlertModalLabel">
              {title}
            </h5>
            <button
              type="button"
              className="btn-close btn-close-white"
              aria-label="Fermer"
              onClick={handleClose}
            />
          </div>
          <div className="modal-body">
            {message && (
              <p style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                {message}
              </p>
            )}
          </div>
          <div className="modal-footer">
            <button
              type="button"
              className={`btn ${buttonClass}`}
              onClick={handleClose}
            >
              Fermer
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CustomAlert;