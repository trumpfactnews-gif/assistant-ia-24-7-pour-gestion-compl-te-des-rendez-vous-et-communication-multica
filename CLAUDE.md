# Assistant IA 24/7 — Gestion des rendez-vous & communication multicanal

## Équipe d'agents

Ce projet embarque le **roster complet de 232 sous-agents** (16 divisions) dans `.claude/agents/`
(voir [`.claude/agents/TEAM.md`](.claude/agents/TEAM.md) pour l'index par division et les agents
les plus pertinents pour ce projet).

Ils proviennent du dépôt [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents)
(licence MIT). Le matériel d'orchestration (playbooks, runbooks, templates de passation, exemples)
est dans [`.claude/agency/`](.claude/agency/).

### Activer un agent
- En conversation : « Active le _<nom de l'agent>_ et … »
- En sous-tâche : lance-le via l'outil Agent avec le sous-agent correspondant.

### Choisir le bon agent
- **Conception du cœur conversationnel** → Prompt Engineer, AI Engineer, Multi-Agent Systems Architect
- **Prise de RDV vocale / téléphonie** → Voice AI Integration Engineer, Backend Architect
- **Canaux email / SMS / réseaux** → Email Marketing Strategist, Multi-Platform Publisher, Content Creator
- **Multilingue** → Language Translator
- **RGPD / conformité** → Data Privacy Officer, Compliance Auditor, Legal Compliance Checker
- **Fiabilité 24/7** → SRE, DevOps Automator

## Statut du projet
Dépôt initialisé avec l'équipe d'agents.

### Sentinelle — backend de détection de fraude par SMS (`sentinelle-backend/`)
Premier module applicatif livré : un microservice **Python/Flask** qui analyse un
message texte et renvoie un verdict de fraude explicable (FR/EN). Il combine des
heuristiques expertes (arnaques canadiennes/québécoises), un classifieur ML
(TF-IDF), une analyse anti-hameçonnage des URL et une base de signalements
communautaire. Couvert par 44 tests, packagé pour Docker.

- Démarrage, API et architecture : [`sentinelle-backend/README.md`](sentinelle-backend/README.md)
- Confidentialité (Loi 25 / LPRPDE) : [`sentinelle-backend/docs/PRIVACY.md`](sentinelle-backend/docs/PRIVACY.md)

### Sentinelle Mobile — app React Native (`sentinelle-mobile/`)
Application mobile (TypeScript) qui intercepte les SMS entrants (module natif
Android), les envoie au backend pour analyse et alerte l'utilisateur. Interface
« bouclier » bilingue, client API typé et testé contre le vrai backend.

- Intégration et exécution : [`sentinelle-mobile/README.md`](sentinelle-mobile/README.md)

> Note : le nom du dépôt évoque la gestion de rendez-vous ; le produit construit
> ici est **Sentinelle** (sécurité numérique). Renommer le dépôt si cette
> orientation est confirmée.
