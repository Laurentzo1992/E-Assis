import React from "react";
import { useParams, Link } from "react-router-dom";
import useApi from "../hooks/useApi";
import Spinner from "../components/ui/Spinner";

/**
 * @file MarcheDetailPage.jsx
 * @description Page de détail complète pour un marché public.
 * Affiche toutes les informations disponibles : détails généraux, appel d'offre,
 * et surtout, la liste des lots avec les entreprises participantes et les résultats.
 */

// Sous-composant pour afficher les détails de l'appel d'offre.
const AppelOffreDetails = ({ appelOffre }) => {
  if (!appelOffre) return null;
  return (
    <div className="card mb-4">
      <div className="card-header">
        <h4>Détails de l'Appel d'Offre</h4>
      </div>
      <div className="card-body">
        <p>
          <strong>Date limite de dépôt :</strong>{" "}
          {new Date(appelOffre.date_depot).toLocaleString("fr-FR")}
        </p>
        <p>
          <strong>Référence du dossier :</strong>{" "}
          {appelOffre.reference_dossier || "N/A"}
        </p>
        <p>
          <strong>Lieu de dépôt :</strong> {appelOffre.lieu_depot || "N/A"}
        </p>
        <p>
          <strong>Cautionnement :</strong>{" "}
          {appelOffre.cautionnement
            ? `${parseFloat(appelOffre.cautionnement).toLocaleString(
                "fr-FR"
              )} FCFA`
            : "N/A"}
        </p>
      </div>
    </div>
  );
};

// Sous-composant pour afficher les détails du résultat global.
const ResultatDetails = ({ resultat }) => {
  if (!resultat) return null;
  return (
    <div className="card mb-4">
      <div className="card-header">
        <h4>Informations sur l'Attribution</h4>
      </div>
      <div className="card-body">
        <p>
          <strong>Date d'attribution :</strong>{" "}
          {new Date(resultat.date_attribution).toLocaleDateString("fr-FR")}
        </p>
        <p>
          <strong>Référence de la décision :</strong>{" "}
          {resultat.reference_decision || "N/A"}
        </p>
        <p>
          <strong>Nombre d'offres reçues :</strong>{" "}
          {resultat.nombre_offres_recues || "N/A"}
        </p>
        <p>
          <strong>Délai d'exécution :</strong>{" "}
          {resultat.delai_execution || "N/A"}
        </p>
      </div>
    </div>
  );
};

// Sous-composant pour afficher le tableau des lots.
const LotsTable = ({ lots }) => {
  if (!lots || lots.length === 0) {
    return (
      <p>Aucune information sur les lots n'est disponible pour ce marché.</p>
    );
  }
  return (
    <div className="card">
      <div className="card-header">
        <h4>Résultats Détaillés par Lot</h4>
      </div>

      {/* Desktop / large screens: table (md and up) */}
      <div className="d-none d-md-block">
        <div className="table-responsive">
          <table className="table table-striped table-hover mb-0">
            <thead className="table-light">
              <tr>
                <th>Lot</th>
                <th>Description</th>
                <th>Entreprise Participante</th>
                <th className="text-end">Montant Proposé</th>
                <th className="text-center">Rang</th>
                <th>Statut</th>
              </tr>
            </thead>
            <tbody>
              {lots.map((lot) => (
                <tr
                  key={lot.id}
                  className={lot.statut === "Retenu" ? "table-success" : ""}
                >
                  <td>{lot.numero_lot || "Unique"}</td>
                  <td>{lot.description || "N/A"}</td>
                  <td>{lot.nom_entreprise_texte}</td>
                  <td className="text-end">
                    {lot.montant_propose
                      ? `${parseFloat(lot.montant_propose).toLocaleString(
                          "fr-FR"
                        )} FCFA`
                      : "N/A"}
                  </td>
                  <td className="text-center">{lot.rang || "N/A"}</td>
                  <td>
                    <span
                      className={`badge ${
                        lot.statut === "Retenu" ? "bg-success" : "bg-secondary"
                      }`}
                    >
                      {lot.statut || "N/D"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Mobile: stacked card list (smaller screens) */}
      <div className="d-block d-md-none">
        <div className="list-group list-group-flush">
          {lots.map((lot) => (
            <div
              key={lot.id}
              className={`list-group-item mb-2 p-3 ${
                lot.statut === "Retenu" ? "border-success" : ""
              }`}
            >
              <div className="d-flex justify-content-between align-items-start mb-2">
                <div>
                  <strong>Lot:</strong> {lot.numero_lot || "Unique"}
                </div>
                <div className="text-end">
                  <span
                    className={`badge ${
                      lot.statut === "Retenu" ? "bg-success" : "bg-secondary"
                    }`}
                  >
                    {lot.statut || "N/D"}
                  </span>
                </div>
              </div>
              <div className="mb-2">
                <strong>Description:</strong> {lot.description || "N/A"}
              </div>
              <div className="mb-2">
                <strong>Entreprise:</strong> {lot.nom_entreprise_texte}
              </div>
              <div className="d-flex justify-content-between">
                <div>
                  <strong>Montant:</strong>{" "}
                  {lot.montant_propose
                    ? `${parseFloat(lot.montant_propose).toLocaleString(
                        "fr-FR"
                      )} FCFA`
                    : "N/A"}
                </div>
                <div>
                  <strong>Rang:</strong> {lot.rang || "N/A"}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// Composant principal de la page.
const MarcheDetailPage = () => {
  const { marcheId } = useParams(); // Récupère l'ID depuis l'URL (ex: /marche/123)
  const endpoint = `backend/marches-details/${marcheId}/`;
  const { data: marche, loading, error } = useApi(endpoint, {}, [marcheId]);

  if (loading) {
    return (
      <div
        className="d-flex justify-content-center align-items-center"
        style={{ height: "100vh" }}
      >
        <Spinner message="Chargement des détails du marché..." />
      </div>
    );
  }
  if (error) {
    return (
      <div className="container mt-4">
        <div className="alert alert-danger">
          <h4>Erreur de chargement</h4>
          <p>Impossible de récupérer les détails de ce marché.</p>
          <pre>{error.message}</pre>
        </div>
      </div>
    );
  }
  if (!marche) {
    return (
      <div className="container mt-4">
        <p>Aucun marché trouvé pour cet identifiant.</p>
      </div>
    );
  }

  return (
    <div className="container my-4">
      <div className="mb-4">
        <Link to="/Dashboard" className="btn btn-outline-secondary">
          ← Retour au Dashboard
        </Link>
      </div>

      <div className="card mb-4">
        <div className="card-header bg-primary text-white">
          <h2 className="mb-0 h4">Marché : {marche.objet}</h2>
        </div>
        <div className="card-body">
          <p>
            <strong>Autorité Contractante :</strong> {marche.ministere}
          </p>
          <p>
            <strong>Région :</strong> {marche.region || "Non spécifiée"}
          </p>
          <p>
            <strong>Type de procédure :</strong> {marche.type_procedure.libelle}
          </p>
          <p>
            <strong>Budget Estimé :</strong>{" "}
            {marche.budget_min
              ? `${parseFloat(marche.budget_min).toLocaleString("fr-FR")} FCFA`
              : "Non communiqué"}
          </p>
          <hr />
          <p className="small text-muted mb-0">
            Source : Publication "{marche.publication.title}" du{" "}
            {new Date(marche.publication.date_publication).toLocaleDateString(
              "fr-FR"
            )}
          </p>
        </div>
      </div>

      <div className="row">
        <div className="col-lg-6">
          <AppelOffreDetails appelOffre={marche.appel_offre} />
        </div>
        <div className="col-lg-6">
          <ResultatDetails resultat={marche.resultat} />
        </div>
      </div>

      <LotsTable lots={marche.lots} />
    </div>
  );
};

export default MarcheDetailPage;
