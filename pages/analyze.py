import streamlit as st

from googleapiclient.discovery import build
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import logging
import trafilatura
import pandas as pd
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from collections import Counter, defaultdict
import nltk
import textstat
import os
import json
import hashlib
from datetime import datetime, timedelta
from nltk.corpus import stopwords
nltk.download('stopwords')


# Configurer le logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("word_count.log"),
        logging.StreamHandler()
    ]
)

# Réinitialiser le cache
cache_lock = threading.Lock()
url_cache = {}

# Dictionnaire global pour stocker les mots et les URLs où ils apparaissent
word_url_map = defaultdict(set)

# Durée de validité du cache (en jours)
CACHE_VALIDITY_DAYS = 14

# Fonction pour générer un haché pour une chaîne donnée (utilisé pour les noms de fichiers)
def generate_hash(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()


def save_google_results_cache(keyphrase, data):
    CACHE_DIR = 'cache'
    GOOGLE_RESULTS_CACHE_DIR = os.path.join(CACHE_DIR, 'google_results')
    # Créer les répertoires de cache s'ils n'existent pas
    os.makedirs(GOOGLE_RESULTS_CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(GOOGLE_RESULTS_CACHE_DIR, f"{generate_hash(keyphrase)}.json")
    data_to_save = {
        'date': datetime.now().isoformat(),
        'data': data
    }
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(data_to_save, f, ensure_ascii=False)
    logging.info(f"Résultats de recherche Google et contenu HTML enregistrés dans le cache pour la keyphrase '{keyphrase}'.")


def load_google_results_cache(keyphrase):
    CACHE_DIR = 'cache'
    GOOGLE_RESULTS_CACHE_DIR = os.path.join(CACHE_DIR, 'google_results')
    cache_file = os.path.join(GOOGLE_RESULTS_CACHE_DIR, f"{generate_hash(keyphrase)}.json")
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            data_loaded = json.load(f)
            cache_date = datetime.fromisoformat(data_loaded['date'])
            if datetime.now() - cache_date < timedelta(days=CACHE_VALIDITY_DAYS):
                logging.info(f"Chargement des résultats de recherche Google depuis le cache pour la keyphrase '{keyphrase}'.")
                return data_loaded['data'], cache_date
            else:
                logging.info(f"Le cache des résultats de recherche Google pour la keyphrase '{keyphrase}' est expiré.")
    return None, None

# Fonction pour récupérer le contenu HTML d'une URL
def fetch_url_content(url, timeout):
    try:
        logging.info(f"Téléchargement de l'URL: {url}")
        response = requests.get(url, timeout=timeout)
        response.encoding = response.apparent_encoding  # Gérer l'encodage
        if response.status_code == 200:
            html_content = response.text.strip()
            return html_content, response.status_code
        else:
            logging.warning(f"Échec de la requête pour l'URL: {url} - Code statut: {response.status_code}")
            return None, response.status_code
    except Exception as e:
        logging.error(f"Erreur lors du téléchargement de l'URL {url}: {e}")
        return None, None


# Fonction pour extraire le contenu principal avec trafilatura
def extract_main_content(html_content):
    try:
        extracted_content = trafilatura.extract(
            html_content,
            include_comments=False,
            include_tables=False,
            output_format='html',
            include_formatting=True,
            favor_recall=True  # Rendre l'extraction plus tolérante
        ) or ''
        return extracted_content.strip()
    except Exception as e:
        logging.error(f"Erreur lors de l'extraction du contenu principal: {e}")
        return ''  # Retourner une chaîne vide en cas d'erreur

# Les autres fonctions (analyze_general_metrics, analyze_content_structure, etc.) restent inchangées

# Fonction principale pour traiter une URL
def fetch_and_analyze(item, timeout, custom_stopwords):
    url, pos = item['url'], item['position']
    html_content = item.get('html_content')  # Récupérer le contenu HTML depuis l'item
    status_code = item.get('status_code', 200)
    cache_date = item.get('cache_date')  # Date du cache des résultats Google

    if not html_content or status_code != 200:
        logging.warning(f"Aucun contenu HTML disponible pour l'URL: {url}")
        return None

    # Analyser le HTML complet
    soup_full = BeautifulSoup(html_content, 'html.parser')

    # Extraire le contenu principal
    extracted_content = extract_main_content(html_content)
    if not extracted_content:
        logging.warning(f"Aucun contenu extrait pour l'URL: {url}")
        return None
    soup_content = BeautifulSoup(extracted_content, 'html.parser')

    # Extraire le texte du contenu extrait
    text = soup_content.get_text(separator=' ', strip=True)

    # Analyser les métriques générales
    general_metrics = analyze_general_metrics(html_content, text)

    # Analyser la structure du contenu
    content_structure = analyze_content_structure(soup_content)

    # Analyser les liens dans le HTML complet
    links_full = analyze_links(soup_full, url)

    # Analyser les liens dans le contenu extrait
    links_content = analyze_links(soup_content, url)

    # Analyser les mots-clés les plus utilisés
    keywords = analyze_keywords(text, content_structure['headings'], custom_stopwords, url)

    # Compilation des résultats
    result = {
        'status_code': status_code,
        'url': url,
        'position': pos,
        'cache_date': cache_date.isoformat() if cache_date else None,
        **general_metrics,
        **content_structure,
        'links_full': links_full,
        'links_content': links_content,
        'most_common_words': keywords['most_common_words'],
        'word_frequency': keywords['word_frequency']  # Inclure toutes les fréquences
    }

    return result

# Fonction principale pour récupérer les données
def get_data(keyphrase, api_key, cx, num_threads=5, request_timeout=10, custom_stopwords=[]):
    # Vérifier si les résultats de recherche Google sont en cache
    cached_results, cache_date = load_google_results_cache(keyphrase)
    if cached_results is not None:
        # Utiliser les données du cache
        items = cached_results
    else:
        # Faire une nouvelle requête à Google
        service = build("customsearch", "v1", developerKey=api_key)

        items = []
        for start_index in [1, 11]:  # Pages 1 et 2
            try:
                res = service.cse().list(
                    q=keyphrase,
                    cx=cx,
                    lr='lang_fr',
                    start=start_index,
                    num=10
                ).execute()
                items.extend(res.get('items', []))
            except Exception as e:
                logging.error(f"Erreur lors de la récupération des résultats de recherche: {e}")
                continue

        # Récupérer le contenu HTML des URLs et les inclure dans les items
        for item in items:
            url = item.get('link')
            if url:
                html_content, status_code = fetch_url_content(url, request_timeout)
                item['html_content'] = html_content
                item['status_code'] = status_code

        # Sauvegarder les résultats de recherche et le contenu HTML dans le cache
        save_google_results_cache(keyphrase, items)
        cache_date = datetime.now()

    urls = []
    position = 1
    for item in items:
        url = item.get('link')
        if url:
            urls.append({
                'url': url,
                'position': position,
                'html_content': item.get('html_content'),
                'status_code': item.get('status_code', 200),
                'cache_date': cache_date
            })
            position += 1

    url_data = []

    # Utiliser ThreadPoolExecutor pour le multi-threading
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        future_to_url = {
            executor.submit(fetch_and_analyze, item, request_timeout, custom_stopwords): item
            for item in urls
        }
        for future in as_completed(future_to_url):
            item = future_to_url[future]
            url = item['url']
            try:
                result = future.result()
                if result:
                    url_data.append(result)
                    logging.info(f"URL traitée avec succès: {url}")
                else:
                    logging.warning(f"Échec du traitement pour l'URL: {url}")
            except Exception as e:
                logging.error(f"Erreur lors du traitement de l'URL {url}: {e}")

    return url_data

# Fonction pour analyser les métriques générales
def analyze_general_metrics(html_content, text):
    # Extraire les métadonnées (title et description)
    soup_full = BeautifulSoup(html_content, 'html.parser')
    meta_title_tag = soup_full.find('title')
    meta_title = meta_title_tag.get_text(strip=True) if meta_title_tag else ''
    meta_description_tag = soup_full.find('meta', attrs={'name': 'description'})
    meta_description = meta_description_tag.get('content', '') if meta_description_tag else ''
    
    # Calcul du score de lisibilité
    readability_score = textstat.flesch_reading_ease(text)
    
    # Compter le nombre de mots
    words = text.split()
    word_count = len(words)
    
    # Limiter la longueur du contenu à 500 caractères
    max_content_length = 500
    content = text[:max_content_length] + '...' if len(text) > max_content_length else text
    
    return {
        'meta_title': meta_title,
        'meta_description': meta_description,
        'readability_score': readability_score,
        'word_count': word_count,
        'content': content
    }

# Fonction pour analyser la structure du contenu
def analyze_content_structure(soup_content):
    # Compter les éléments dans le contenu extrait
    num_paragraphs = len(soup_content.find_all('p'))
    num_tables = len(soup_content.find_all('table'))
    num_lists = len(soup_content.find_all(['ul', 'ol']))
    num_images = len(soup_content.find_all('img'))
    
    # Extraire les titres (h1 à h6) avec leur niveau
    headings = []
    for heading_tag in soup_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        level = heading_tag.name
        text_heading = heading_tag.get_text(separator=' ', strip=True)
        headings.append({'level': level, 'text': text_heading})
    
    # Compter le nombre de chaque type de titre
    heading_counts = {
        'h1': len(soup_content.find_all('h1')),
        'h2': len(soup_content.find_all('h2')),
        'h3': len(soup_content.find_all('h3')),
        'h4': len(soup_content.find_all('h4')),
        'h5': len(soup_content.find_all('h5')),
        'h6': len(soup_content.find_all('h6')),
    }
    
    # Compter le nombre total de hx (h2 à h6)
    total_hx = sum(heading_counts[h] for h in ['h2', 'h3', 'h4', 'h5', 'h6'])
    
    return {
        'num_paragraphs': num_paragraphs,
        'num_tables': num_tables,
        'num_lists': num_lists,
        'num_images': num_images,
        'headings': headings,
        'heading_counts': heading_counts,
        'total_hx': total_hx
    }

# Fonction pour analyser les liens
def analyze_links(soup, url):
    internal_links = []
    external_links = []
    domain = urlparse(url).netloc.lower()
    
    for link_tag in soup.find_all('a', href=True):
        href = link_tag['href']
        anchor_text = link_tag.get_text(strip=True)
        href = urljoin(url, href)  # Convertir les liens relatifs en absolus
        parsed_href = urlparse(href)
        link_domain = parsed_href.netloc.lower()
        if link_domain == domain:
            internal_links.append({'href': href, 'anchor': anchor_text})
        else:
            external_links.append({'href': href, 'anchor': anchor_text})
    
    num_internal_links = len(set([link['href'] for link in internal_links]))
    num_external_links = len(set([link['href'] for link in external_links]))
    
    return {
        'num_internal_links': num_internal_links,
        'num_external_links': num_external_links,
        'internal_links': internal_links,
        'external_links': external_links
    }

# Fonction pour analyser les mots-clés les plus utilisés
def analyze_keywords(text, headings, custom_stopwords, url):
    # Intégrer les stopwords français et la liste personnalisée
    stop_words = set(stopwords.words('french'))
    custom_stopwords_set = set(custom_stopwords)
    all_stopwords = stop_words.union(custom_stopwords_set)
    
    combined_text = text + ' ' + ' '.join([h['text'] for h in headings])
    words_filtered = [word for word in combined_text.lower().split() if word not in all_stopwords and word.isalpha()]
    
    # Mettre à jour le dictionnaire des mots et des URLs
    for word in set(words_filtered):
        word_url_map[word].add(url)
    
    word_frequency = Counter(words_filtered)
    most_common_words = word_frequency.most_common(10)  # Top 10 des mots les plus utilisés pour cette page
    
    # **Retourner les fréquences de tous les mots pour chaque URL**
    return {
        'most_common_words': most_common_words,
        'word_frequency': word_frequency
    }

# Exemple d'utilisation
if __name__ == "__main__":
    # Remplacez 'VOTRE_CLE_API_GOOGLE' et 'VOTRE_ID_MOTEUR_DE_RECHERCHE' par vos propres valeurs
    api_key = st.secrets["cse_api_key"]
    cx = st.secrets["cse_api_key"]
    keyphrase = 'agence nounou lille'

    # Liste personnalisée de stopwords
    custom_stopwords = ['uns', 'unes', 'exemple']

    # Initialiser le dictionnaire global des mots et des URLs
    word_url_map = defaultdict(set)
    
    url_data = get_data(
        keyphrase,
        api_key,
        cx,
        num_threads=10,
        request_timeout=15,
        custom_stopwords=custom_stopwords
    )

    # Créer un DataFrame avec les détails par URL
    df = pd.DataFrame(url_data)

    # Supprimer les entrées avec status_code None
    df = df[df['status_code'].notnull()]
   
    # Trier le DataFrame par position pour refléter l'ordre de la SERP
    df = df.sort_values('position')

    # Convertir les listes en chaînes de caractères pour l'affichage
    def links_to_str(links):
        return ', '.join([f"{link['anchor']} ({link['href']})" for link in links])

    df['internal_links_full'] = df['links_full'].apply(lambda x: links_to_str(x['internal_links']))
    df['external_links_full'] = df['links_full'].apply(lambda x: links_to_str(x['external_links']))
    df['internal_links_content'] = df['links_content'].apply(lambda x: links_to_str(x['internal_links']))
    df['external_links_content'] = df['links_content'].apply(lambda x: links_to_str(x['external_links']))
    df['headings'] = df['headings'].apply(lambda hs: ', '.join([f"{h['level']}: {h['text']}" for h in hs]))
    df['most_common_words'] = df['most_common_words'].apply(lambda words: ', '.join([f"{word} ({count})" for word, count in words]))

    # Séparer les DataFrames pour présenter les informations de manière structurée

    # Fonction pour créer le DataFrame des métriques générales
    def create_main_dataframe(df):
        return df[[
            'position', 'url', 'status_code', 'word_count',
            'readability_score', 'meta_title', 'meta_description', 'content'
        ]]
    
    # Fonction pour créer le DataFrame de la structure du contenu
    def create_structure_dataframe(df):
        return df[[
            'position', 'url', 'num_paragraphs', 'num_tables', 'num_lists', 'num_images',
            'total_hx', 'headings'
        ]]
    
    # Fonction pour créer le DataFrame des liens (HTML complet)
    def create_links_full_dataframe(df):
        return df[[
            'position', 'url', 'links_full'
        ]]
    
    # Fonction pour créer le DataFrame des liens (contenu extrait)
    def create_links_content_dataframe(df):
        return df[[
            'position', 'url', 'links_content'
        ]]
    
    # Fonction pour créer le DataFrame des mots-clés les plus utilisés
    def create_keywords_dataframe(df):
        return df[[
            'position', 'url', 'most_common_words'
        ]]
    
    # Créer les DataFrames
    df_main = create_main_dataframe(df)
    df_structure = create_structure_dataframe(df)
    df_links_full = create_links_full_dataframe(df)
    df_links_content = create_links_content_dataframe(df)
    df_keywords = create_keywords_dataframe(df)
    
    # **Créer le DataFrame des mots les plus utilisés globalement**
    
    # Calculer la fréquence totale des mots sur toutes les URLs
    global_word_frequency = Counter()
    for result in url_data:
        word_freq = result.get('word_frequency', Counter())
        global_word_frequency.update(word_freq)
    
    # Filtrer les mots qui apparaissent dans au moins 3 URLs distinctes
    words_in_multiple_urls = {word for word, urls in word_url_map.items() if len(urls) >= 3}
    
    # Préparer les données pour le DataFrame
    data = []
    for word in words_in_multiple_urls:
        freq_total = global_word_frequency[word]
        num_urls = len(word_url_map[word])
        freq_avg = freq_total / num_urls
        data.append({
            'Mot': word,
            'Nombre d\'URLs': num_urls,
            'Fréquence Totale': freq_total,
            'Fréquence Moyenne par Page': freq_avg
        })
    
    # Créer le DataFrame
    df_global_keywords = pd.DataFrame(data)
    
    # Trier le DataFrame par 'Fréquence Totale' décroissante
    df_global_keywords = df_global_keywords.sort_values(by='Fréquence Totale', ascending=False)
    
    # Réordonner les colonnes
    df_global_keywords = df_global_keywords[['Mot', 'Nombre d\'URLs', 'Fréquence Totale', 'Fréquence Moyenne par Page']]

    # Afficher les DataFrames
    pd.set_option('display.max_columns', None)
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_colwidth', None)

    st.write("\n=== Métriques Générales ===")
    st.dataframe(df_main)

    st.write("\n=== Structure du Contenu ===")
    st.dataframe(df_structure)

    st.write("\n=== Liens dans le HTML Complet ===")
    st.dataframe(df_links_full)

    st.write("\n=== Liens dans le Contenu Extrait ===")
    st.dataframe(df_links_content)

    st.write("\n=== Mots-Clés les Plus Utilisés par Page ===")
    st.dataframe(df_keywords)

    st.write("\n=== Mots les Plus Utilisés Globalement (dans au moins 3 URLs) ===")
    st.dataframe(df_global_keywords)

    # # Exporter les DataFrames en CSV
    # df_main.to_csv('resultats_generaux.csv', index=False)
    # df_structure.to_csv('resultats_structure.csv', index=False)
    # df_links_full.to_csv('resultats_liens_html_complet.csv', index=False)
    # df_links_content.to_csv('resultats_liens_contenu_extrait.csv', index=False)
    # df_keywords.to_csv('resultats_mots_cles_par_page.csv', index=False)
    # df_global_keywords.to_csv('resultats_mots_cles_global.csv', index=False)
