import os
import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from collections import Counter
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Tuple
from collections import defaultdict

custom_stopwords = {
    "a", "abord", "absolument", "afin", "ah", "ai", "aie", "ailleurs", "ainsi",
    "ait", "allaient", "allo", "allons", "allô", "alors", "anterieur",
    "anterieure", "anterieures", "apres", "après", "as", "assez", "attendu",
    "au", "aucun", "aucune", "aujourd", "aujourd'hui", "aupres", "auquel",
    "aura", "auraient", "aurait", "auront", "aussi", "autre", "autrefois",
    "autrement", "autres", "autrui", "aux", "auxquelles", "auxquels",
    "avaient", "avais", "avait", "avant", "avec", "avoir", "avons", "ayant",
    "bah", "bas", "basee", "bat", "beau", "beaucoup", "bien", "bigre", "boum",
    "bravo", "brrr", "c'", "car", "ce", "ceci", "cela", "celle", "celle-ci",
    "celle-là", "celles", "celles-ci", "celles-là", "celui", "celui-ci",
    "celui-là", "cent", "cependant", "certain", "certaine", "certaines",
    "certains", "certes", "ces", "cet", "cette", "ceux", "ceux-ci", "ceux-là",
    "chacun", "chacune", "chaque", "cher", "chers", "chez", "chiche", "chut",
    "chère", "chères", "ci", "cinq", "cinquantaine", "cinquante",
    "cinquantième", "cinquième", "clac", "clic", "combien", "comme", "comment",
    "comparable", "comparables", "compris", "concernant", "contre", "couic",
    "crac", "c’", "d'", "da", "dans", "de", "debout", "dedans", "dehors",
    "deja", "delà", "depuis", "dernier", "derniere", "derriere", "derrière",
    "des", "desormais", "desquelles", "desquels", "dessous", "dessus", "deux",
    "deuxième", "deuxièmement", "devant", "devers", "devra", "different",
    "differentes", "differents", "différent", "différente", "différentes",
    "différents", "dire", "directe", "directement", "dit", "dite", "dits",
    "divers", "diverse", "diverses", "dix", "dix-huit", "dix-neuf", "dix-sept",
    "dixième", "doit", "doivent", "donc", "dont", "douze", "douzième", "dring",
    "du", "duquel", "durant", "dès", "désormais", "d’", "effet", "egale",
    "egalement", "egales", "eh", "elle", "elle-même", "elles", "elles-mêmes",
    "en", "encore", "enfin", "entre", "envers", "environ", "es", "est", "et",
    "etaient", "etais", "etait", "etant", "etc", "etre", "eu", "euh", "eux",
    "eux-mêmes", "exactement", "excepté", "extenso", "exterieur", "fais",
    "faisaient", "faisant", "fait", "façon", "feront", "fi", "flac", "floc",
    "font", "gens", "ha", "hein", "hem", "hep", "hi", "ho", "holà", "hop",
    "hormis", "hors", "hou", "houp", "hue", "hui", "huit", "huitième", "hum",
    "hurrah", "hé", "hélas", "i", "il", "ils", "importe", "j'", "je", "jusqu",
    "jusque", "juste", "j’", "l'", "la", "laisser", "laquelle", "las", "le",
    "lequel", "les", "lesquelles", "lesquels", "leur", "leurs", "longtemps",
    "lors", "lorsque", "lui", "lui-meme", "lui-même", "là", "lès", "l’", "m'",
    "ma", "maint", "maintenant", "mais", "malgre", "malgré", "maximale", "me",
    "meme", "memes", "merci", "mes", "mien", "mienne", "miennes", "miens",
    "mille", "mince", "minimale", "moi", "moi-meme", "moi-même", "moindres",
    "moins", "mon", "moyennant", "même", "mêmes", "m’", "n'", "na", "naturel",
    "naturelle", "naturelles", "ne", "neanmoins", "necessaire",
    "necessairement", "neuf", "neuvième", "ni", "nombreuses", "nombreux",
    "non", "nos", "notamment", "notre", "nous", "nous-mêmes", "nouveau", "nul",
    "néanmoins", "nôtre", "nôtres", "n’", "o", "oh", "ohé", "ollé", "olé",
    "on", "ont", "onze", "onzième", "ore", "ou", "ouf", "ouias", "oust",
    "ouste", "outre", "ouvert", "ouverte", "ouverts", "où", "paf", "pan",
    "par", "parce", "parfois", "parle", "parlent", "parler", "parmi",
    "parseme", "partant", "particulier", "particulière", "particulièrement",
    "pas", "passé", "pendant", "pense", "permet", "personne", "peu", "peut",
    "peuvent", "peux", "pff", "pfft", "pfut", "pif", "pire", "plein", "plouf",
    "plus", "plusieurs", "plutôt", "possessif", "possessifs", "possible",
    "possibles", "pouah", "pour", "pourquoi", "pourrais", "pourrait",
    "pouvait", "prealable", "precisement", "premier", "première",
    "premièrement", "pres", "probable", "probante", "procedant", "proche",
    "près", "psitt", "pu", "puis", "puisque", "pur", "pure", "qu'", "quand",
    "quant", "quant-à-soi", "quanta", "quarante", "quatorze", "quatre",
    "quatre-vingt", "quatrième", "quatrièmement", "que", "quel", "quelconque",
    "quelle", "quelles", "quelqu'un", "quelque", "quelques", "quels", "qui",
    "quiconque", "quinze", "quoi", "quoique", "qu’", "rare", "rarement",
    "rares", "relative", "relativement", "remarquable", "rend", "rendre",
    "restant", "reste", "restent", "restrictif", "retour", "revoici",
    "revoilà", "rien", "s'", "sa", "sacrebleu", "sait", "sans", "sapristi",
    "sauf", "se", "sein", "seize", "selon", "semblable", "semblaient",
    "semble", "semblent", "sent", "sept", "septième", "sera", "seraient",
    "serait", "seront", "ses", "seul", "seule", "seulement", "si", "sien",
    "sienne", "siennes", "siens", "sinon", "six", "sixième", "soi", "soi-même",
    "soit", "soixante", "son", "sont", "sous", "souvent", "specifique",
    "specifiques", "speculatif", "stop", "strictement", "subtiles",
    "suffisant", "suffisante", "suffit", "suis", "suit", "suivant", "suivante",
    "suivantes", "suivants", "suivre", "superpose", "sur", "surtout", "s’",
    "t'", "ta", "tac", "tant", "tardive", "te", "tel", "telle", "tellement",
    "telles", "tels", "tenant", "tend", "tenir", "tente", "tes", "tic", "tien",
    "tienne", "tiennes", "tiens", "toc", "toi", "toi-même", "ton", "touchant",
    "toujours", "tous", "tout", "toute", "toutefois", "toutes", "treize",
    "trente", "tres", "trois", "troisième", "troisièmement", "trop", "très",
    "tsoin", "tsouin", "tu", "té", "t’", "un", "une", "unes", "uniformement",
    "unique", "uniques", "uns", "va", "vais", "vas", "vers", "via", "vif",
    "vifs", "vingt", "vivat", "vive", "vives", "vlan", "voici", "voilà",
    "vont", "vos", "votre", "vous", "vous-mêmes", "vu", "vé", "vôtre",
    "vôtres", "zut", "à", "â", "ça", "ès", "étaient", "étais", "était",
    "étant", "été", "être", "ô", "...", "…", ";", ":", "-", "/", "?", "!", "d’une", "d’un"
}
french_stopwords = custom_stopwords


def analyze_co_occurrences(text, target_words, window_size=5):
    words = text.lower().split()
    co_occurrences = {word: defaultdict(int) for word in target_words}

    for i, word in enumerate(words):
        if word in target_words:
            start = max(0, i - window_size)
            end = min(len(words), i + window_size + 1)
            for j in range(start, end):
                if i != j and words[j] not in french_stopwords:
                    co_occurrences[word][words[j]] += 1

    return co_occurrences


def get_page_content(url: str) -> str:
    """
    Récupère le contenu textuel d'une page web.

    Args:
        url (str): L'URL de la page à récupérer.

    Returns:
        str: Le contenu textuel de la page.
    """
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        return ' '.join([p.text for p in soup.find_all('p')])
    except requests.RequestException as e:
        print(f"Erreur lors de la récupération de la page {url}: {e}")
        return ''


def get_serp_semantic_field(query: str, api_key: str, cse_id: str, num_results: int = 20, num_words: int = 75) -> Tuple[Dict[str, int], Dict[str, int], Dict[str, Dict[str, int]]]:
    """
    Extrait le champ sémantique et les entités nommées à partir des résultats de recherche Google.

    Args:
        query (str): La requête de recherche.
        api_key (str): Clé API Google.
        cse_id (str): ID du moteur de recherche personnalisé.
        num_results (int): Nombre de résultats à analyser.
        num_words (int): Nombre de mots à inclure dans le champ sémantique.

    Returns:
        tuple: (champ sémantique, entités nommées)
    """
    service = build("customsearch", "v1", developerKey=api_key)

    results_text = ""
    urls = []

    for start in range(1, num_results, 10):
        try:
            result = service.cse().list(q=query, cx=cse_id, start=start, num=10).execute()
            for item in result.get('items', []):
                text = f"{item['title']} {item['snippet']} "
                results_text += text
                urls.append(item['link'])
        except Exception as e:
            print(f"Erreur lors de la récupération des résultats de recherche: {e}")

    # Utilisation de ThreadPoolExecutor pour paralléliser les requêtes HTTP
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(get_page_content, url): url for url in urls}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                page_content = future.result()
                results_text += page_content
            except Exception as exc:
                print(f"Une erreur s'est produite lors du traitement de {url}: {exc}")

    words = results_text.lower().split()
    word_counts = Counter(words)
    semantic_field = {word: count for word, count in word_counts.items() if word not in french_stopwords and len(word) > 3}

    # Trier le champ sémantique et prendre les 10 premiers mots
    sorted_semantic_field = dict(sorted(semantic_field.items(), key=lambda x: x[1], reverse=True)[:num_words])
    top_10_words = list(sorted_semantic_field.keys())[:10]

    co_occurrences = analyze_co_occurrences(results_text, top_10_words)

    return (
        dict(sorted(semantic_field.items(), key=lambda x: x[1], reverse=True)[:num_words]),
        co_occurrences
    )


def main():
    st.title("Analyse sémantique de recherche Google")

    STREAMLIT_ENV = os.environ.get("STREAMLIT_ENV", "dev")
    if STREAMLIT_ENV == "dev":
        cse_api_key = st.secrets["cse_api_key"]
        cse_id = st.secrets["cse_id"]
    else:
        with st.sidebar:
            st.sidebar.cse_api_key = st.text_input("Clé API CSE", type="password")
            st.sidebar.cse_id = st.text_input("ID CSE")

    query = st.text_input("Entrez votre requête de recherche :", "quel disjoncteur pour un lave vaisselle ?")

    if st.button("Analyser"):
        if not STREAMLIT_ENV and (not cse_api_key or not cse_id):
            st.error("Veuillez entrer une clé API et un ID CSE valides.")
        else:
            with st.spinner("Analyse en cours..."):
                semantic_field, co_occurrences = get_serp_semantic_field(
                    query, cse_api_key, cse_id
                )
                st.subheader(f"Champ sémantique étendu pour '{query}':")
                st.table(pd.DataFrame(list(semantic_field.items()), columns=["Mot", "Fréquence"]))

                st.subheader("Co-occurrences pour les mots cibles:")
                for target_word, related_words in co_occurrences.items():
                    st.write(f"**{target_word.capitalize()}:**")
                    top_related = dict(sorted(related_words.items(), key=lambda x: x[1], reverse=True)[:10])
                    st.table(pd.DataFrame(list(top_related.items()), columns=["Mot associé", "Fréquence"]))


if __name__ == "__main__":
    main()
