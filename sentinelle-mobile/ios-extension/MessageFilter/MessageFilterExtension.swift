//
//  MessageFilterExtension.swift
//  Sentinelle — extension de filtrage SMS pour iOS
//
//  iOS n'autorise PAS l'interception silencieuse des SMS. Le seul mécanisme
//  natif est une « SMS Filter Extension » (framework IdentityLookup) qui :
//    • ne s'applique qu'aux messages d'expéditeurs INCONNUS (hors contacts) ;
//    • décide de classer le message (Junk / Promotion / Transaction) ou de
//      laisser passer ;
//    • peut, au besoin, déférer la décision à un service réseau (notre backend),
//      via l'URL déclarée dans Info.plist (ILMessageFilterExtensionNetworkURL).
//
//  Stratégie : d'abord une analyse HORS LIGNE (rapide, 100 % privée, aucune
//  donnée ne quitte l'appareil) ; si elle n'est pas concluante, on défère au
//  réseau (qui appelle le moteur Sentinelle complet).
//

import Foundation
import IdentityLookup

final class MessageFilterExtension: ILMessageFilterExtension {}

extension MessageFilterExtension: ILMessageFilterQueryHandling {

    func handle(_ queryRequest: ILMessageFilterQueryRequest,
                context: ILMessageFilterExtensionContext,
                completion: @escaping (ILMessageFilterQueryResponse) -> Void) {

        let offline = Self.offlineAction(for: queryRequest.messageBody ?? "")

        switch offline {
        case .junk, .allow:
            // Décision prise sur l'appareil, sans réseau.
            let response = ILMessageFilterQueryResponse()
            response.action = offline
            completion(response)

        default:
            // Indéterminé : déférer au moteur Sentinelle via le réseau.
            context.deferQueryRequestToNetwork { (networkResponse, _) in
                let response = ILMessageFilterQueryResponse()
                if let data = networkResponse?.data,
                   let action = Self.action(fromServerData: data) {
                    response.action = action
                } else {
                    response.action = .none
                }
                completion(response)
            }
        }
    }

    // MARK: - Analyse hors ligne (sous-ensemble compact des heuristiques backend)

    /// Renvoie `.junk` si fortement frauduleux, `.allow` si manifestement sûr,
    /// `.none` si indéterminé (→ déférer au réseau).
    static func offlineAction(for body: String) -> ILMessageFilterAction {
        let text = body.lowercased()
        if text.isEmpty { return .allow }

        var score = 0

        // Signaux quasi certains.
        if matchesAny(text, ["carte cadeau", "gift card", "google play card", "itunes card"]) {
            score += 4
        }
        // Demande d'identifiants / code secret.
        if matchesAny(text, ["mot de passe", "code de vérification", "votre nip", "numéro de carte",
                              "verification code", "card number", "social insurance", "votre nas"]) {
            score += 3
        }
        // Marques usurpées fréquentes au Canada + lien.
        let brandHit = matchesAny(text, ["desjardins", "interac", "revenu québec", "arc ",
                                         "service canada", "postes canada", "canada post", "407etr", "407 etr"])
        let hasLink = text.contains("http://") || text.contains("https://") || matchesAny(text, [".xyz", ".top", ".click", "bit.ly", "tinyurl"])
        if brandHit && hasLink { score += 3 }
        // Urgence / menace.
        if matchesAny(text, ["immédiatement", "dans les 24", "compte bloqué", "compte suspendu",
                             "mandat d'arrestation", "account suspended", "within 24", "act now"]) {
            score += 2
        }
        // Appât.
        if matchesAny(text, ["vous avez gagné", "félicitations", "you won", "congratulations", "réclamez votre prix"]) {
            score += 2
        }

        if score >= 4 {
            return .junk
        }
        if score == 0 {
            return .allow
        }
        return .none  // ambigu → déférer au réseau
    }

    private static func matchesAny(_ text: String, _ needles: [String]) -> Bool {
        for n in needles where text.contains(n) {
            return true
        }
        return false
    }

    // MARK: - Réponse du service réseau

    /// Le backend (`ILMessageFilterExtensionNetworkURL`) renvoie un JSON :
    /// `{ "action": "junk" | "promotion" | "transaction" | "allow" | "none" }`.
    static func action(fromServerData data: Data) -> ILMessageFilterAction? {
        guard
            let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let raw = obj["action"] as? String
        else {
            return nil
        }
        switch raw.lowercased() {
        case "junk": return .junk
        case "allow": return .allow
        case "promotion":
            if #available(iOS 14.0, *) { return .promotion }
            return .junk
        case "transaction":
            if #available(iOS 14.0, *) { return .transaction }
            return .allow
        default: return ILMessageFilterAction.none
        }
    }
}
