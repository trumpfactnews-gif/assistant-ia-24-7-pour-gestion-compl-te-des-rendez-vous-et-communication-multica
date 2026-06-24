# 🎭 L'Agence — Roster complet (232 agents)

Roster **complet** des agents installés dans `.claude/agents/`, issu du dépôt
[msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) (licence MIT).
Chaque fichier `.md` est un sous-agent Claude Code activable.

> **Activer un agent** : dans une session Claude Code, demande p. ex.
> _« Active le Backend Architect et conçois le schéma de réservation des RDV »_,
> ou lance-le comme sous-agent via l'outil Agent.

## Divisions (16)

| Division | Agents | Exemples |
|----------|:------:|----------|
| 💻 Engineering | 33 | Backend/Software Architect, AI Engineer, Voice AI, Email Intelligence, DevOps, SRE |
| 📣 Marketing | 36 | Email/Social Strategist, Content Creator, Multi-Platform Publisher, SEO |
| ✨ Specialized | 53 | Customer Service/Success, Data Privacy Officer, Language Translator, Workflow Architect |
| 🎮 Game Development | 20 | Unity, Unreal, Godot, Roblox, level design |
| 🗺️ GIS | 13 | Cartographie, géospatial, spatial analysis |
| 🛡️ Security | 10 | AppSec, Compliance Auditor, Pentester, Threat Detection |
| 🎨 Design | 9 | UX Architect, UI Designer, UX Researcher, Brand Guardian |
| 📈 Sales | 9 | Deal/Account Strategist, Sales Engineer, Pipeline Analyst |
| 🧪 Testing | 8 | API Tester, Accessibility Auditor, Performance Benchmarker |
| 📋 Project Management | 7 | Senior PM, Meeting Notes, Project Shepherd, Jira Steward |
| 🎯 Paid Media | 7 | Campagnes payantes, acquisition |
| 🛟 Support | 6 | Support Responder, Analytics Reporter, Legal Compliance |
| 🥽 Spatial Computing | 6 | VisionOS, XR, AR/VR |
| 🎓 Academic | 5 | Recherche, rédaction académique |
| 💵 Finance | 5 | Modélisation financière, comptabilité |
| 📦 Product | 5 | Product Manager, Sprint Prioritizer, Feedback Synthesizer |

**Total : 232 agents.**

## ⭐ Les plus pertinents pour CE projet (RDV + communication multicanal)

- **Conversationnel / IA** : `engineering-prompt-engineer`, `engineering-ai-engineer`, `engineering-multi-agent-systems-architect`
- **Prise de RDV vocale / téléphonie** : `engineering-voice-ai-integration-engineer`, `engineering-backend-architect`
- **Email / canaux** : `engineering-email-intelligence-engineer`, `marketing-email-strategist`, `marketing-multi-platform-publisher`
- **Multilingue** : `language-translator`
- **Support client** : `support-support-responder`, `customer-service`, `customer-success-manager`
- **RGPD / conformité** : `data-privacy-officer`, `security-compliance-auditor`, `support-legal-compliance-checker`
- **Fiabilité 24/7** : `engineering-sre`, `engineering-devops-automator`
- **Cadrage** : `product-manager`, `engineering-software-architect`, `specialized-workflow-architect`

## 🎼 Orchestration

Le dossier [`.claude/agency/`](../agency/) contient le matériel d'orchestration du dépôt source :
- `strategy/QUICKSTART.md` et `strategy/EXECUTIVE-BRIEF.md`
- `strategy/playbooks/` — phases 0→6 (discovery → operate)
- `strategy/runbooks/` — scénarios (MVP, campagne marketing, incident, feature entreprise)
- `strategy/coordination/` — prompts d'activation & templates de passation (handoff)
- `examples/` — workflows multi-agents de référence
