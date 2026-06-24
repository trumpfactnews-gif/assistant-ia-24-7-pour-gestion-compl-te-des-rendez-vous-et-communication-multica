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
Dépôt initialisé avec l'équipe d'agents. Le code applicatif reste à construire —
commence par solliciter le **Software Architect** et le **Product Manager** pour cadrer.
