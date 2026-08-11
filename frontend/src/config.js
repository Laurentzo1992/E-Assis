// URL de base de l'API - REACT_APP_API_URL est injectee au build (Create React App n'expose que
// les variables prefixees REACT_APP_, inlinees statiquement dans le bundle). Sans elle (dev local),
// retombe sur l'API tournant dans docker-compose sur la machine du developpeur. En production,
// definir REACT_APP_API_URL=https://api.mondomaine.tld avant `npm run build` (ou dans l'environment
// du service frontend si le build se fait au demarrage du conteneur) - sinon le bundle continuerait
// d'appeler 127.0.0.1:8000, injoignable depuis le navigateur d'un vrai visiteur.
export const API_BASE_URL = process.env.REACT_APP_API_URL || "http://127.0.0.1:8000";
