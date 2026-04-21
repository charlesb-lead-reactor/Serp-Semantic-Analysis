import streamlit as st
import math
import os

def split_csv(file_content, header, max_size_bytes):
    """
    Divise le contenu d'un fichier CSV en plusieurs parties ne dépassant pas max_size_bytes.
    Chaque partie commence par l'en-tête.

    Args:
        file_content (str): Contenu complet du fichier CSV.
        header (str): Ligne d'en-tête du CSV.
        max_size_bytes (int): Taille maximale de chaque partie en octets.

    Returns:
        List[str]: Liste des contenus des fichiers divisés.
    """
    lines = file_content.splitlines()
    split_files = []
    current_file = header + "\n"
    current_size = len(current_file.encode('utf-8'))

    for line in lines[1:]:  # Ignorer le premier ligne car c'est l'en-tête
        line_with_newline = line + "\n"
        line_size = len(line_with_newline.encode('utf-8'))
        
        # Si ajouter cette ligne dépasse la taille maximale, créer un nouveau fichier
        if current_size + line_size > max_size_bytes:
            split_files.append(current_file)
            current_file = header + "\n" + line_with_newline
            current_size = len(current_file.encode('utf-8'))
        else:
            current_file += line_with_newline
            current_size += line_size

    # Ajouter le dernier fichier s'il contient des données
    if current_file.strip():
        split_files.append(current_file)

    return split_files

def generate_part_filename(original_name, part_number):
    """
    Génère le nom du fichier divisé en conservant l'extension originale à la fin.

    Args:
        original_name (str): Nom original du fichier.
        part_number (int): Numéro de la partie.

    Returns:
        str: Nom du fichier divisé.
    """
    base, ext = os.path.splitext(original_name)
    return f"{base}.part{part_number}{ext}"

def main():
    st.set_page_config(page_title="Diviseur de CSV", layout="wide")
    st.title("Diviseur de Fichiers CSV")

    st.write("""
        Cette application vous permet de télécharger un fichier CSV, de spécifier une taille limite, 
        puis de diviser le fichier en plusieurs fichiers ne dépassant pas la taille spécifiée. 
        Chaque fichier divisé inclura l'en-tête original.
    """)

    # Téléchargement du fichier
    uploaded_file = st.file_uploader("Choisissez un fichier CSV à diviser", type=["csv"])

    if uploaded_file is not None:
        try:
            # Lire le contenu du fichier en tant que texte
            file_content = uploaded_file.read().decode('utf-8')
            lines = file_content.splitlines()

            if len(lines) < 2:
                st.error("Le fichier CSV doit contenir au moins deux lignes (en-tête et une ligne de données).")
                st.stop()

            header = lines[0]
            data_lines = lines[1:]

            # Afficher les informations du fichier
            file_details = {
                "Nom": uploaded_file.name,
                "Taille": f"{len(file_content.encode('utf-8')) / (1024 * 1024):.2f} MB",
                "Nombre de lignes": len(lines)
            }
            st.write("### Informations du fichier")
            st.json(file_details)

            # Spécification de la taille limite
            st.write("### Spécifiez la taille limite pour chaque partie")
            max_size_mb = st.number_input("Taille maximale par fichier (MB)", min_value=1, value=5, step=1)

            # Initialiser les variables dans session_state si elles n'existent pas
            if 'split_files' not in st.session_state:
                st.session_state.split_files = None
            if 'original_filename' not in st.session_state:
                st.session_state.original_filename = ""

            if st.button("Diviser le fichier"):
                with st.spinner("Division en cours..."):
                    # Convertir la taille maximale en octets
                    max_size_bytes = max_size_mb * 1024 * 1024

                    # Diviser le fichier
                    split_files = split_csv(file_content, header, max_size_bytes)

                    # Stocker les parties et le nom original dans session_state
                    st.session_state.split_files = split_files
                    st.session_state.original_filename = uploaded_file.name
                    st.success(f"Fichier divisé en {len(split_files)} partie(s).")

            # Afficher les boutons de téléchargement pour chaque partie si les parties sont disponibles
            if st.session_state.split_files is not None:
                st.write("### Télécharger les parties")
                for idx, part in enumerate(st.session_state.split_files, start=1):
                    part_name = generate_part_filename(st.session_state.original_filename, idx)
                    st.download_button(
                        label=f"Télécharger Partie {idx}",
                        data=part,
                        file_name=part_name,
                        mime='text/csv'
                    )

                # Optionnel : Afficher une vérification des tailles
                st.write("### Vérification des tailles des parties")
                for idx, part in enumerate(st.session_state.split_files, start=1):
                    part_size_mb = len(part.encode('utf-8')) / (1024 * 1024)
                    st.write(f"**Partie {idx}** : {part_size_mb:.2f} MB")
        except UnicodeDecodeError:
            st.error("Le fichier téléchargé n'est pas un fichier texte encodé en UTF-8.")
    else:
        st.info("Veuillez télécharger un fichier CSV pour commencer.")

if __name__ == "__main__":
    main()
