FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
# --legacy-peer-deps : i18next 26.x declare un peerOptional typescript ^5-7 (support de
# l'inference de types), en conflit avec le typescript ^3-4 attendu par react-scripts 5.0.1 (CRA,
# pas de TypeScript utilise dans ce projet - le conflit ne porte que sur cette dependance
# transitive, jamais executee) - conflit connu et sans consequence dans l'ecosysteme CRA.
RUN npm ci --legacy-peer-deps

COPY . .

# Sur un volume monte depuis l'hote Windows/Mac, les evenements natifs du systeme de fichiers ne
# remontent pas jusqu'au conteneur Linux - sans repasser en polling, le live-reload ne se declenche
# jamais. react-scripts 5 (webpack 5) utilise watchpack (WATCHPACK_POLLING, defini dans
# docker-compose.yml) pour son propre watcher de compilation ; CHOKIDAR_USEPOLLING reste ici pour
# les outils annexes (ex. eslint) qui s'appuient sur chokidar directement.
ENV CHOKIDAR_USEPOLLING=true

EXPOSE 3000

CMD ["npm", "start"]
