// Tarif de l'abonnement (prix annuel, duree d'essai) - lu depuis l'API plutot que fige en dur
// cote frontend, pour rester synchronise avec la table tarifs_abonnement geree via /admin.
import { API_BASE_URL } from "../config";

export async function fetchTarif() {
  const response = await fetch(`${API_BASE_URL}/api/paiement/tarif/`);
  if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);
  return response.json();
}
