// Configuration i18next pour le support multilingue (FR/EN/Moore).
// Detection : localStorage (choix memorise) -> langue du navigateur -> repli sur le francais.
// Le detecteur cache automatiquement le choix dans localStorage sous la cle "i18nextLng".
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

import fr from "./locales/fr/translation.json";
import en from "./locales/en/translation.json";
import mos from "./locales/mos/translation.json";

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      fr: { translation: fr },
      en: { translation: en },
      mos: { translation: mos },
    },
    fallbackLng: "fr",
    supportedLngs: ["fr", "en", "mos"],
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
    },
    interpolation: {
      escapeValue: false, // React échappe déjà par défaut
    },
  });

export default i18n;
