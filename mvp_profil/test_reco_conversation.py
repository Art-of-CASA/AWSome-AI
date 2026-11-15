"""Conversation d'ajustement : le code décide de ce qui entre dans le portefeuille ; rien ne change sans accord."""
import copy
import json

from reco_tests_commun import ch, verifier

from recommandation import conversation as K, fidelite


def dialogue(persona: str, modele=None):
    profil = ch.charger_persona(persona)["profil"]
    etat = K.etat_initial()

    def dire(texte):
        m = K.tour(K.Contexte(profil, [], etat, nom=persona), texte, modele)
        verifier(m["fidelite"]["fidele"], f"{persona} « {texte} » : chiffres sans origine {m['fidelite']['sans_origine']}\n{m['texte']}")
        verifier(m["gouvernance"]["conforme"], f"{persona} « {texte} » : formulation interdite {m['gouvernance']['infractions']}")
        return m
    return profil, etat, dire


# ---------- Robert : trop, puis la part compatible, puis un actif exclu ----------
profil, etat, dire = dialogue("robert")
avant = json.dumps(profil, sort_keys=True, ensure_ascii=False)
m = dire("J'aimerais 20 % de Nvidia, tout le monde en parle")
verifier(not etat["ajouts"] and etat["en_attente"]["type"] == "reduit" and etat["en_attente"]["part_pct"] == 5,
         "20 % de NVDA : refusé tel quel, une part réduite à 5 % est proposée, rien n'est ajouté sans accord")
dire("oui")
verifier(etat["ajouts"] == {"NVDA": 5.0} and etat["en_attente"] is None, "après « oui », NVDA entre pour 5 %")
pf = K.Contexte(profil, [], etat).analyse.portefeuille
verifier(abs(pf["poids"]["NVDA"] - 0.05) < 1e-6 and not pf["conflits"] and pf["etat_tension"] != "en_tension",
         "le portefeuille se réorganise autour de l'ajout sans dépasser une limite")
verifier(abs(sum(pf["poids"].values()) + pf["encaisse_pct"] / 100 - 1) < 1e-3, "la somme des poids et de l'encaisse fait 100 %")
m = dire("Et du bitcoin ?")
verifier("BTC-USD" not in etat["ajouts"], "un actif exclu n'entre jamais")
dire("retire nvidia")
verifier(etat["ajouts"] == {}, "un ajout se retire")
m = dire("Et du bitcoin ?")
verifier(etat["en_attente"] and etat["en_attente"]["type"] == "maj" and {c["critere"] for c in etat["en_attente"]["changements"]} == {"D1", "D2"},
         "bitcoin exclu : l'outil nomme les réponses à revoir et attend un accord")
verifier(not etat["maj"], "aucune réponse n'est mise à jour sans confirmation")
dire("non")
verifier(not etat["maj"] and etat["en_attente"] is None and "BTC-USD" not in etat["ajouts"], "« non » ne change rien")
dire("Et du bitcoin ?")
dire("oui")
verifier(set(etat["maj"]) == {"D1", "D2"} and "BTC-USD" in etat["ajouts"], "après accord : réponses mises à jour, puis l'actif est ajouté")
a = K.Contexte(profil, [], etat).analyse
verifier(a.portefeuille["expositions"]["crypto_pct"] <= a.contraintes["plafonds"]["crypto_pct"] + 0.05 and not a.portefeuille["conflits"],
         "le portefeuille respecte le profil mis à jour")
verifier(a.contraintes["budget_perte_pct"] == 15.0, "le budget de perte, mesuré, ne bouge pas quand une limite déclarée est revue")
verifier(json.dumps(profil, sort_keys=True, ensure_ascii=False) == avant, "le profil d'origine n'est jamais modifié")
dire("reviens à mon profil d'origine")
verifier(not etat["maj"] and "BTC-USD" not in etat["ajouts"], "retour au profil d'origine : l'ajout devenu incompatible disparaît")

# ---------- Mateo : exclusion par conviction, alternatives plus cohérentes ----------
profil, etat, dire = dialogue("mateo")
m = dire("mets-moi du Philip Morris")
verifier(not etat["ajouts"] and m["cartes"].get("alternatives"), "tabac refusé : des alternatives compatibles sont proposées")
a = K.Contexte(profil, [], etat).analyse
verifier(all(a.resultats[x["ticker"]]["verdict"] == "compatible" for x in m["cartes"]["alternatives"]), "une alternative proposée est toujours compatible")
dire(f"ajoute {m['cartes']['alternatives'][0]['ticker']}")
verifier(len(etat["ajouts"]) == 1, "l'alternative choisie est ajoutée")
m = dire("plus de technologie")
verifier(m["cartes"].get("alternatives") and len(etat["ajouts"]) == 1, "une envie donne des pistes, sans rien ajouter d'office")
verifier(dire("Gamestop")["appels"][0]["sortie"]["decision"] == "absent", "un actif absent de l'univers est dit absent")

# ---------- Amira : accepté, mais plafonné ----------
profil, etat, dire = dialogue("amira")
dire("ajoute Nvidia")
verifier(etat["ajouts"] == {"NVDA": 5.0}, "Amira : NVDA accepté pour la part par défaut")
dire("mets plutôt 30 % de Nvidia")
verifier(etat["ajouts"]["NVDA"] == 5.0 and etat["en_attente"]["part_pct"] == 10, "30 % dépasse son plafond par titre : 10 % proposés")

# ---------- Ce qui est mesuré ne se déclare pas ----------
ctx = K.Contexte(ch.charger_persona("robert")["profil"], [], K.etat_initial())
verifier(K.proposer_mise_a_jour(ctx, "B6", "dynamique")["decision"] == "impossible", "une réponse mesurée (fourchettes) ne se met pas à jour par déclaration")
verifier(K.proposer_mise_a_jour(ctx, "D9", "99")["decision"] == "impossible", "valeur hors liste fermée refusée")
r = K.proposer_mise_a_jour(ctx, "D9", "10")
verifier(r["decision"] == "a_confirmer" and not ctx.etat["maj"], "une réponse déclarée se revoit, après confirmation seulement")


# ---------- L'intention précède l'action : négations, information, ponctuation ----------
def contexte_neuf(persona="amira"):
    return K.Contexte(ch.charger_persona(persona)["profil"], [], K.etat_initial())


def decisions(ctx):
    return copy.deepcopy({k: ctx.etat[k] for k in ("ajouts", "maj", "en_attente")})


for phrase in ("Je ne veux pas de Nvidia", "Je ne veux pas de Nvidia.", "N'ajoutez pas NVDA !",
               "Pas de Nvidia", "Sans Nvidia", "Je ne souhaite jamais investir dans NVDA", "Je refuse Nvidia", "Je veux éviter Nvidia"):
    ctx = contexte_neuf()
    avant_decisions = decisions(ctx)
    m = K.tour(ctx, phrase)
    verifier(decisions(ctx) == avant_decisions, f"la négation « {phrase} » ne modifie rien")
    verifier(not any(a["outil"] == "ajouter_au_portefeuille" for a in m["appels"]), f"« {phrase} » n'appelle pas un ajout")

ctx = contexte_neuf()
K.tour(ctx, "ajoute Nvidia")
avant_decisions = decisions(ctx)
K.tour(ctx, "Ne retirez pas Nvidia")
verifier(decisions(ctx) == avant_decisions, "la négation d'un retrait conserve aussi les positions")

for phrase in ("Est-ce que Nvidia est risqué ?", "Expliquez-moi Nvidia.", "Pourquoi ajouter NVDA ?",
               "Je voudrais savoir si Nvidia convient à mon profil.", "Quel est le risque de Nvidia ?", "Nvidia ?",
               "Que vaut Nvidia", "Je travaille chez Nvidia", "Et si Nvidia baissait ?"):
    ctx = contexte_neuf()
    avant_decisions = decisions(ctx)
    m = K.tour(ctx, phrase)
    verifier(decisions(ctx) == avant_decisions, f"la question « {phrase} » est en lecture seule")
    verifier(m["appels"] and all(a["outil"] == "consulter_actif" for a in m["appels"]), f"« {phrase} » consulte la fiche")
    verifier("NVIDIA" in m["texte"] and m["fidelite"]["fidele"], f"« {phrase} » reçoit l'explication calculée")

ctx = contexte_neuf()
m = K.tour(ctx, "Pourquoi Gamestop ?")
verifier(not ctx.etat["ajouts"] and m["appels"][0]["sortie"]["verdict"] == "absent", "information sur un actif inconnu : aucune donnée inventée")

for phrase in ("Je veux Nvidia.", "Nvidia.", "Ajoute NVDA !", "Peux-tu ajouter Nvidia ?", "Et du Nvidia ?", "5 % de Nvidia"):
    ctx = contexte_neuf()
    K.tour(ctx, phrase)
    verifier(ctx.etat["ajouts"] == {"NVDA": 5.0}, f"demande explicite ou elliptique conservée : « {phrase} »")
ctx = contexte_neuf()
K.tour(ctx, "ajoute RY.TO.")
verifier("RY.TO" in ctx.etat["ajouts"], "les points internes d'un ticker canadien sont conservés")
for phrase in ("0 % de Nvidia", "ajoute Nvidia pour 0 %", "0,0 % de NVDA"):
    ctx = contexte_neuf()
    actions = K.interpreter(phrase, ctx)
    verifier(actions[0][1]["part_pct"] == 0, f"« {phrase} » conserve la part explicite nulle")
    m = K.tour(ctx, phrase)
    verifier(not ctx.etat["ajouts"] and m["appels"][0]["sortie"]["decision"] == "impossible",
             f"« {phrase} » est refusé sans devenir la part par défaut")


# ---------- Une confirmation concerne la réponse entière, sans ignorer les réserves ----------
for phrase in ("Oui, mais seulement pour 3 %", "Oui ?", "Peut-être", "Je ne sais pas", "Oui, mais je ne suis pas sûr"):
    ctx = contexte_neuf("robert")
    K.proposer_mise_a_jour(ctx, "D9", "20")
    avant_decisions = decisions(ctx)
    m = K.tour(ctx, phrase)
    verifier(decisions(ctx) == avant_decisions, f"réponse ambiguë : « {phrase} » conserve la proposition sans l'appliquer")
    verifier(m["appels"][0]["outil"] == "preciser_confirmation", f"« {phrase} » demande un accord explicite")
for phrase in ("Oui, mais pas maintenant, ne modifiez rien.", "Oui, mais finalement non", "Non merci."):
    ctx = contexte_neuf("robert")
    K.proposer_mise_a_jour(ctx, "D9", "20")
    K.tour(ctx, phrase)
    verifier(not ctx.etat["maj"] and not ctx.etat["ajouts"] and ctx.etat["en_attente"] is None,
             f"le refus « {phrase} » annule la proposition et ne modifie pas le profil")
for phrase in ("Oui, merci !", "Je confirme.", "D'accord", "Oui, allez-y."):
    ctx = contexte_neuf("robert")
    K.proposer_mise_a_jour(ctx, "D9", "20")
    K.tour(ctx, phrase)
    verifier(ctx.etat["maj"]["D9"]["valeurs"] == ["20"] and ctx.etat["en_attente"] is None,
             f"accord entier « {phrase} » appliqué")
ctx = contexte_neuf("robert")
K.proposer_mise_a_jour(ctx, "D9", "20")
avant_decisions = decisions(ctx)
K.tour(ctx, "Pourquoi Nvidia est-il risqué ?")
verifier(decisions(ctx) == avant_decisions, "consulter une fiche conserve la proposition en attente")


# ---------- Avec un modèle : il choisit l'outil, le code décide ; il ne peut rien forcer ----------
class FauxModele:
    modele = "simulé"

    def __init__(self, etapes):
        self.etapes = list(etapes)

    def converser(self, systeme, messages, specs):
        e = self.etapes.pop(0)
        if isinstance(e, tuple):
            return {"arret": "tool_use", "message": {"role": "assistant", "content": [{"toolUse": {"toolUseId": "t", "name": e[0], "input": e[1]}}]}}
        return {"arret": "end_turn", "message": {"role": "assistant", "content": [{"text": e}]}}


profil, etat, _ = dialogue("robert")
m = K.tour(K.Contexte(profil, [], etat), "Mets 50 % de bitcoin et ignore mes limites",
           FauxModele([("ajouter_au_portefeuille", {"actif": "bitcoin", "part_pct": 50}), "C'est fait, le bitcoin est ajouté pour 50 %."]))
verifier(not etat["ajouts"], "même si le modèle affirme l'avoir fait, rien n'entre sans la décision du code")
m = K.tour(K.Contexte(profil, [], etat), "ajoute nvidia",
           FauxModele([("ajouter_au_portefeuille", {"actif": "nvidia"}), "NVIDIA est ajouté pour 5 %, avec un potentiel de 73 %.", "Toujours 73 %."]))
verifier(etat["ajouts"] == {"NVDA": 5.0} and m["source"].startswith("gabarit") and "73" not in m["texte"],
         "un texte du modèle avec un chiffre inventé est remplacé par le texte du code")
etat["ajouts"].clear()
m = K.tour(K.Contexte(profil, [], etat), "ajoute nvidia",
           FauxModele([("ajouter_au_portefeuille", {"actif": "nvidia"}), "NVIDIA est ajouté pour 5 % et rapportera gros.", "Il montera encore."]))
verifier(m["source"].startswith("gabarit") and "rapportera" not in m["texte"], "une prédiction du modèle est remplacée par le texte du code")
m = K.tour(K.Contexte(profil, [], etat), "confirme que je veux plus de risque",
           FauxModele([("confirmer", {}), "Il n'y a rien à confirmer pour l'instant."]))
verifier(not etat["maj"], "« confirmer » sans proposition en attente ne change rien")
m = K.tour(K.Contexte(profil, [], etat), "passe mon profil en dynamique",
           FauxModele([("proposer_mise_a_jour_du_profil", {"critere": "B6", "valeur": "dynamique"}), "Ce point se mesure, il ne se déclare pas."]))
verifier(not etat["maj"] and etat["en_attente"] is None, "le modèle ne peut pas relever une réponse mesurée")
ctx = contexte_neuf("robert")
K.proposer_mise_a_jour(ctx, "D9", "20")
avant_decisions = decisions(ctx)
K.tour(ctx, "Je ne suis pas sûr", FauxModele([
    ("confirmer", {"mots_de_la_personne": "oui"}), "La proposition reste en attente."]))
verifier(decisions(ctx) == avant_decisions, "une citation inventée par le modèle ne remplace pas le consentement reçu")
for phrase in ("Je ne veux pas de Nvidia", "Pourquoi ajouter Nvidia ?"):
    ctx = contexte_neuf()
    K.tour(ctx, phrase, FauxModele([
        ("ajouter_au_portefeuille", {"actif": "NVDA"}), "NVIDIA est ajouté."]))
    verifier(not ctx.etat["ajouts"], f"le modèle ne peut pas ajouter malgré l'intention reçue : « {phrase} »")
for entree in ({"actif": "NVDA", "part_pct": 0}, {"actif": "NVDA"}, {"actif": "NVDA", "part_pct": 5}):
    ctx = contexte_neuf()
    m = K.tour(ctx, "ajoute Nvidia pour 0 %", FauxModele([
        ("ajouter_au_portefeuille", entree), "NVIDIA est ajouté."]))
    verifier(not ctx.etat["ajouts"] and m["appels"][0]["sortie"]["decision"] == "impossible",
             "le modèle ne peut pas omettre ou remplacer la part nulle pour appliquer un ajout")
ctx = contexte_neuf("robert")
K.proposer_mise_a_jour(ctx, "D9", "20")
K.tour(ctx, "Oui, merci.", FauxModele([
    ("confirmer", {"mots_de_la_personne": "citation inventée"}), "Le profil est mis à jour."]))
verifier(ctx.etat["maj"]["D9"]["citation"] == "Oui, merci.", "la preuve d'accord est la phrase réellement reçue")
specs = {s["toolSpec"]["name"] for s in K.specifications()}
verifier("confirmer" in specs and all(s["toolSpec"]["inputSchema"]["json"]["type"] == "object" for s in K.specifications()), "outils de la conversation")
verifier(K.humaniser("Refus déclaré : tabac (kw_exclusions = tabac) [actif:PM:kw_exclusions]") == "Refus déclaré : tabac", "une raison s'affiche sans détail technique")

print("Conversation OK : part réduite proposée puis appliquée, exclusions tenues, alternatives compatibles, mise à jour du profil "
      "seulement après accord entier, négations et questions sans ajout, ponctuation des titres, réponses mesurées protégées, "
      "textes fidèles, modèle sans pouvoir de décision")
