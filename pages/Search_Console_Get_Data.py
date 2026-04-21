# import streamlit as st
# from google.oauth2 import service_account
# from googleapiclient.discovery import build
# from google.cloud import bigquery
# import pandas as pd
# from datetime import timedelta
# import os
# import io


# SCOPES = [
#     "https://www.googleapis.com/auth/webmasters",
#     "https://www.googleapis.com/auth/devstorage.read_write",
#     "https://www.googleapis.com/auth/indexing",
#     "https://www.googleapis.com/auth/spreadsheets",
#     "https://www.googleapis.com/auth/bigquery",
# ]

# # Configuration des quotas (si nécessaire)
# QPD_QUOTA = 10_000_000
# QPM_QUOTA = 15_000
# API_CALLS_PER_REQUEST = 10

# # Définir le quota restant (peut être utilisé pour gérer les appels API)
# if 'qpd_remaining' not in st.session_state:
#     st.session_state.qpd_remaining = QPD_QUOTA
# if 'qpm_remaining' not in st.session_state:
#     st.session_state.qpm_remaining = QPM_QUOTA

# # Charger les informations du compte de service depuis st.secrets
# JSON_KEY = {
#     "type": "service_account",
#     "project_id": "lr-searchconsoe",
#     "private_key_id": st.secrets["indexing_googleapis_private_key_id"],
#     "private_key": st.secrets["indexing_googleapis_private_key"],
#     "client_email": st.secrets["indexing_googleapis_client_email"],
#     "client_id": st.secrets["indexing_googleapis_client_id"],
#     "auth_uri": "https://accounts.google.com/o/oauth2/auth",
#     "token_uri": "https://oauth2.googleapis.com/token",
#     "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
#     "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/lr-search-console-api%40lr-searchconsoe.iam.gserviceaccount.com",
# }

# # Créer les identifiants à partir des informations du compte de service
# credentials = service_account.Credentials.from_service_account_info(
#     JSON_KEY, scopes=SCOPES
# )

# # Créer le client pour l'API Search Console
# service = build('searchconsole', 'v1', credentials=credentials)

# # Créer le client pour BigQuery
# bq_client = bigquery.Client(credentials=credentials, project=credentials.project_id)

# def split_and_download_csv(df, max_size_mb=99):
#     # Convertir la taille max en octets
#     max_size_bytes = max_size_mb * 1024 * 1024

#     # Initialisation
#     part_number = 1
#     current_chunk = pd.DataFrame()
#     current_size = 0
#     chunks = []

#     # Lire le DataFrame en morceaux et écrire dans plusieurs fichiers si la taille dépasse
#     for _, row in df.iterrows():
#         # Convertir la ligne en DataFrame
#         row_df = pd.DataFrame([row])
#         current_chunk = pd.concat([current_chunk, row_df], ignore_index=True)

#         # Calculer la taille approximative du chunk accumulé
#         current_size = current_chunk.memory_usage(deep=True).sum()

#         if current_size >= max_size_bytes:
#             # Convertir en CSV le DataFrame actuel (chunk)
#             csv_buffer = io.StringIO()
#             current_chunk.to_csv(csv_buffer, index=False)
#             chunks.append((f"search_console_data_part_{part_number}.csv", csv_buffer.getvalue()))
#             part_number += 1
#             current_chunk = pd.DataFrame()  # Réinitialiser le chunk
#             current_size = 0

#     # Ajouter le dernier chunk s'il reste des données
#     if not current_chunk.empty:
#         csv_buffer = io.StringIO()
#         current_chunk.to_csv(csv_buffer, index=False)
#         chunks.append((f"search_console_data_part_{part_number}.csv", csv_buffer.getvalue()))

#     return chunks


# def get_properties(service):
#     try:
#         site_list = service.sites().list().execute()
#         properties = [site['siteUrl'] for site in site_list.get('siteEntry', [])]
#         properties_sorted = sorted(properties, key=lambda x: x.lower())
#         return properties_sorted
#     except Exception as e:
#         st.error(f"Erreur lors de la récupération des propriétés : {e}")
#         return []


# def get_search_console_data(service, site_url, start_date, end_date):
#     global qpd_remaining, qpm_remaining  # Déclaration globale en premier
#     all_data = []
#     current_date = start_date
#     search_type = 'WEB'
#     while current_date <= end_date:
#         if st.session_state.qpd_remaining <= 0 or st.session_state.qpm_remaining <= 0:
#             st.error("Quota dépassé. Arrêt des requêtes.")
#             break
#         try:
#             request = {
#                 'startDate': current_date.strftime('%Y-%m-%d'),
#                 'endDate': current_date.strftime('%Y-%m-%d'),
#                 'dimensions': ['date', 'query', 'page', 'device', 'country'],
#                 'searchType': search_type,
#                 'rowLimit': 25000
#             }
#             # Suppression du paramètre searchType='web' car non supporté
#             response = service.searchanalytics().query(
#                 siteUrl=site_url,
#                 body=request
#             ).execute()

#             # Transformer la réponse en DataFrame
#             rows = response.get('rows', [])
#             for row in rows:
#                 dimensions = row.get('keys', [])

#                 # Récupérer les impressions et la position moyenne
#                 impressions = row.get('impressions', 0)
#                 average_position = row.get('position', 0)

#                 # Calculer sum_position
#                 # sum_position = (average_position * impressions) - 1 if impressions > 0 else 0
#                 sum_position = (average_position * impressions) if impressions > 0 else 0

#                 data = {
#                     'data_date': dimensions[0] if len(dimensions) > 0 else None,
#                     'site_url': site_url,
#                     'url': dimensions[2] if len(dimensions) > 0 else None,
#                     'query': dimensions[1] if len(dimensions) > 0 else None,
#                     'country': dimensions[4] if len(dimensions) > 0 else None,
#                     'search_type': search_type,
#                     'device': dimensions[3] if len(dimensions) > 0 else None,
#                     'impressions': impressions,
#                     'clicks': row.get('clicks', 0),
#                     'sum_position': sum_position
#                 }
#                 all_data.append(data)

#             # Mise à jour des quotas
#             st.session_state.qpd_remaining -= 1
#             st.session_state.qpm_remaining -= 1

#             current_date += timedelta(days=1)
#         except Exception as e:
#             st.error(f"Erreur lors de la récupération des données pour le {current_date.strftime('%Y-%m-%d')} : {e}")
#             current_date += timedelta(days=1)

#     df = pd.DataFrame(all_data)

#     if 'data_date' in df.columns:
#         df['data_date'] = pd.to_datetime(df['data_date']).dt.date

#     int_fields = ['impressions', 'clicks', 'sum_position']

#     for field in int_fields:
#         if field in df.columns:
#             df[field] = df[field].astype(int)

#     return df


# # Interface Streamlit
# st.title("Exportateur de Données Google Search Console vers BigQuery (Données Journalières)")

# st.write("""
#     Cette application permet de récupérer les données de Google Search Console jour par jour et de les importer directement dans une table BigQuery.
# """)

# # Récupérer les propriétés
# properties = get_properties(service)

# if not properties:
#     st.warning("Aucune propriété trouvée ou erreur lors de la récupération des propriétés.")
# else:
#     selected_property = st.selectbox("Sélectionnez une propriété", options=properties)

#     if selected_property:
#         start_date = st.sidebar.date_input("Date de début", value=pd.to_datetime('2023-01-01'))
#         end_date = st.sidebar.date_input("Date de fin", value=pd.to_datetime('today'))

#         if start_date <= end_date:
#             if st.button("Récupérer les données"):
#                 with st.spinner('Récupération des données...'):
#                     df = get_search_console_data(service, selected_property, start_date, end_date)
#                     if not df.empty:
#                         st.session_state['df'] = df  # Stocker dans la session
#                         st.success("Données récupérées avec succès !")
#                         st.dataframe(df)

#                         # Ajout du bouton pour télécharger le DataFrame au format CSV
#                         csv = df.to_csv(index=False)  # Convertir le DataFrame en CSV
#                         st.download_button(
#                             label="Télécharger les données en CSV",
#                             data=csv,
#                             file_name='search_console_data.csv',
#                             mime='text/csv',
#                         )


#             # Si les données sont déjà stockées dans la session, les afficher
#             if 'df' in st.session_state:
#                 df = st.session_state['df']
#                 st.dataframe(df)

#             st.code(""" 
#             MERGE `lr-sf-cloud-crawler.searchconsole_la_clinique_du_pied_fr.searchdata_url_impression` T
# USING `lr-sf-cloud-crawler.searchconsole_la_clinique_du_pied_fr.20240106` S
# ON T.data_date = S.data_date
#    AND T.site_url = S.site_url
#    AND T.url = S.url
#    AND T.query = S.query
#    AND T.country = S.country
#    AND T.search_type = S.search_type
#    AND T.device = S.device
# WHEN MATCHED THEN
#   UPDATE SET
#     T.query = S.query,
#     T.country = S.country,
#     T.search_type = S.search_type,
#     T.device = S.device,
#     T.impressions = S.impressions,
#     T.clicks = S.clicks,
#     T.sum_position = S.sum_position
# WHEN NOT MATCHED THEN
#   INSERT (data_date, site_url, url, query, country, search_type, device, impressions, clicks, sum_position)
#   VALUES (data_date, site_url, url, query, country, search_type, device, impressions, clicks, sum_position);
#         """)
#         else:
#             st.sidebar.error("La date de début ne peut pas être après la date de fin.")


import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.cloud import bigquery
import pandas as pd
from datetime import timedelta

# Définir les scopes nécessaires
SCOPES = [
    "https://www.googleapis.com/auth/webmasters",
]

# Charger les informations du compte de service depuis st.secrets
JSON_KEY = {
    "type": "service_account",
    "project_id": "lr-searchconsoe",
    "private_key_id": st.secrets["indexing_googleapis_private_key_id"],
    "private_key": st.secrets["indexing_googleapis_private_key"],
    "client_email": st.secrets["indexing_googleapis_client_email"],
    "client_id": st.secrets["indexing_googleapis_client_id"],
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/lr-search-console-api%40lr-searchconsoe.iam.gserviceaccount.com",
}

# Créer les identifiants à partir des informations du compte de service
credentials = service_account.Credentials.from_service_account_info(
    JSON_KEY, scopes=SCOPES
)

# Créer le client pour l'API Search Console
service = build('searchconsole', 'v1', credentials=credentials)

# Créer le client pour BigQuery
bq_client = bigquery.Client(credentials=credentials, project=credentials.project_id)

def get_properties(service):
    try:
        site_list = service.sites().list().execute()
        properties = [site['siteUrl'] for site in site_list.get('siteEntry', [])]
        return sorted(properties, key=lambda x: x.lower())
    except Exception as e:
        st.error(f"Erreur lors de la récupération des propriétés : {e}")
        return []

def get_search_console_data(service, site_url, start_date, end_date, search_type):
    all_data = []
    current_date = start_date
    while current_date <= end_date:
        try:
            request = {
                'startDate': current_date.strftime('%Y-%m-%d'),
                'endDate': current_date.strftime('%Y-%m-%d'),
                'dimensions': ['date', 'query', 'page', 'device', 'country'],
                'searchType': search_type,
                'rowLimit': 25000
            }
            response = service.searchanalytics().query(
                siteUrl=site_url,
                body=request
            ).execute()

            rows = response.get('rows', [])
            for row in rows:
                dimensions = row.get('keys', [])
                data = {
                    'data_date': dimensions[0] if len(dimensions) > 0 else None,
                    'site_url': site_url,
                    'url': dimensions[2] if len(dimensions) > 2 else None,
                    'query': dimensions[1] if len(dimensions) > 1 else None,
                    'country': dimensions[4] if len(dimensions) > 4 else None,
                    'search_type': search_type,
                    'device': dimensions[3] if len(dimensions) > 3 else None,
                    'impressions': row.get('impressions', 0),
                    'clicks': row.get('clicks', 0),
                    'sum_position': row.get('position', 0) * row.get('impressions', 0) if row.get('impressions', 0) > 0 else 0
                }
                all_data.append(data)

            current_date += timedelta(days=1)
        except Exception as e:
            st.error(f"Erreur lors de la récupération des données pour le {current_date.strftime('%Y-%m-%d')} : {e}")
            current_date += timedelta(days=1)

    df = pd.DataFrame(all_data)

    if 'data_date' in df.columns:
        df['data_date'] = pd.to_datetime(df['data_date']).dt.date

    int_fields = ['impressions', 'clicks', 'sum_position']
    for field in int_fields:
        if field in df.columns:
            df[field] = df[field].astype(int)

    return df

# Interface Streamlit
st.title("Exportateur de Données Google Search Console vers BigQuery")

st.write("""
    Cette application permet de récupérer les données de Google Search Console et de les importer directement dans une table BigQuery.
""")

# Récupérer les propriétés
properties = get_properties(service)

if not properties:
    st.warning("Aucune propriété trouvée ou erreur lors de la récupération des propriétés.")
else:
    selected_property = st.selectbox("Sélectionnez une propriété", options=properties)

    if selected_property:
        # Ajout du select pour le type de recherche dans la sidebar
        search_type = st.sidebar.selectbox(
            "Type de recherche",
            options=["WEB", "IMAGE", "VIDEO", "NEWS"],
            index=0
        )

        start_date = st.sidebar.date_input("Date de début", value=pd.to_datetime('2023-01-01'))
        end_date = st.sidebar.date_input("Date de fin", value=pd.to_datetime('today'))

        if start_date <= end_date:
            if st.button("Récupérer les données"):
                with st.spinner('Récupération des données...'):
                    df = get_search_console_data(service, selected_property, start_date, end_date, search_type)
                    if not df.empty:
                        st.session_state['df'] = df  # Stocker dans la session
                        st.success("Données récupérées avec succès !")
                        st.dataframe(df)

                        # Bouton pour télécharger le DataFrame au format CSV
                        csv = df.to_csv(index=False)
                        st.download_button(
                            label="Télécharger les données en CSV",
                            data=csv,
                            file_name='search_console_data.csv',
                            mime='text/csv',
                        )
        else:
            st.sidebar.error("La date de début ne peut pas être après la date de fin.")

    # Optionnel : Afficher le DataFrame si déjà stocké dans la session
    if 'df' in st.session_state:
        df = st.session_state['df']
        st.dataframe(df)

        st.code(""" 
MERGE `lr-sf-cloud-crawler.searchconsole_la_clinique_du_pied_fr.searchdata_url_impression` T
USING `lr-sf-cloud-crawler.searchconsole_la_clinique_du_pied_fr.20240106` S
ON T.data_date = S.data_date
   AND T.site_url = S.site_url
   AND T.url = S.url
   AND T.query = S.query
   AND T.country = S.country
   AND T.search_type = S.search_type
   AND T.device = S.device
WHEN MATCHED THEN
  UPDATE SET
    T.query = S.query,
    T.country = S.country,
    T.search_type = S.search_type,
    T.device = S.device,
    T.impressions = S.impressions,
    T.clicks = S.clicks,
    T.sum_position = S.sum_position
WHEN NOT MATCHED THEN
  INSERT (data_date, site_url, url, query, country, search_type, device, impressions, clicks, sum_position)
  VALUES (data_date, site_url, url, query, country, search_type, device, impressions, clicks, sum_position);
        """)
