import React from "react";
import { useTranslation } from "react-i18next";
import { apiRequest, getTokens } from "../services/auth";
import { API_BASE_URL } from "../config";

// Clé locale utilisée par Dashboard.jsx pour savoir qu'un choix de langue explicite a ete
// fait sur CET appareil, et ne doit donc pas etre ecrase par la synchronisation compte -> appareil
// au chargement (cf. point 8 du plan multilingue).
export const LANGUE_SYNC_DONE_KEY = "langue_sync_done";

const LANGUES = [
  { code: "fr", labelKey: "common.languages.fr" },
  { code: "en", labelKey: "common.languages.en" },
  { code: "mos", labelKey: "common.languages.mos" },
];

/**
 * Selecteur de langue (FR/EN/Moore). Change la langue localement (i18next + localStorage via le
 * detecteur) et, si l'utilisateur est connecte, synchronise le choix avec son compte en
 * best-effort (fire-and-forget) pour qu'il retrouve sa langue sur un autre appareil.
 */
export default function LanguageSwitcher({ className = "" }) {
  const { t, i18n } = useTranslation();

  const handleChange = (e) => {
    const code = e.target.value;
    i18n.changeLanguage(code);
    // Marque ce choix comme volontaire sur cet appareil : le futur effet de synchronisation du
    // Dashboard ne doit pas l'ecraser au prochain chargement avec la langue enregistree en base.
    try {
      localStorage.setItem(LANGUE_SYNC_DONE_KEY, "1");
    } catch (storageError) {
      // localStorage indisponible (mode prive strict, etc.) : pas bloquant pour le changement local.
    }

    const { accessToken } = getTokens();
    if (accessToken) {
      apiRequest(`${API_BASE_URL}/api/auth/profile/`, {
        method: "PUT",
        body: JSON.stringify({ langue: code }),
      }).catch(() => {
        // Best-effort : la synchronisation compte peut echouer (backend indisponible, champ pas
        // encore deploye, etc.) sans jamais bloquer le changement de langue local de l'utilisateur.
      });
    }
  };

  return (
    <select
      className={`form-select form-select-sm language-switcher ${className}`}
      value={i18n.resolvedLanguage || i18n.language}
      onChange={handleChange}
      aria-label={t("common.languageLabel")}
      style={{ width: "95px", flex: "0 0 auto", display: "inline-block" }}
    >
      {LANGUES.map((langue) => (
        <option
          key={langue.code}
          value={langue.code}
          // L'avertissement moore va en title (infobulle au survol) plutot que concatene au
          // libelle affiche : un texte d'option long elargit la largeur du <select> natif dans la
          // plupart des navigateurs, meme quand une autre option est selectionnee.
          title={langue.code === "mos" ? t("common.mooreAvertissement") : undefined}
        >
          {t(langue.labelKey)}
        </option>
      ))}
    </select>
  );
}
