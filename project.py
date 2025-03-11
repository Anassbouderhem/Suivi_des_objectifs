import streamlit as st
import pandas as pd
from fpdf import FPDF
import datetime
import os
import numpy as np
from scipy.optimize import linprog
import altair as alt
import plotly.express as px

# --- Chemin des fichiers ---
USERS_CSV = "users.csv"
OBJECTIFS_CSV = "objectifs.csv"

# --- Configuration ---
st.set_page_config(page_title="Gestion des Objectifs", layout="wide")

# --- Initialisation ---
def init_app():
    if not os.path.exists(USERS_CSV):
        pd.DataFrame({"username": ["admin"], "password": ["password"]}).to_csv(USERS_CSV, index=False)
    if "users_df" not in st.session_state:
        st.session_state.users_df = pd.read_csv(USERS_CSV)

    if "current_user" not in st.session_state:
        st.session_state.current_user = None

    if "data" not in st.session_state:
        st.session_state.data = {}

    # Création/lecture de objectifs.csv + ajout de la colonne check_in si besoin
    if not os.path.exists(OBJECTIFS_CSV):
        df_objectifs = pd.DataFrame(columns=["user", "objectif", "etape_nom", "etape_temps", "etape_deadline", "check_in"])
        df_objectifs.to_csv(OBJECTIFS_CSV, index=False)

    if "objectifs_df" not in st.session_state:
        st.session_state.objectifs_df = pd.read_csv(OBJECTIFS_CSV, parse_dates=["etape_deadline"])
        if "check_in" not in st.session_state.objectifs_df.columns:
            st.session_state.objectifs_df["check_in"] = "no"

# --- Sauvegardes ---
def save_users():
    try:
        st.session_state.users_df.to_csv(USERS_CSV, index=False)
    except PermissionError as e:
        st.error(f"Permission denied: {e}")

def save_objectifs():
    st.session_state.objectifs_df.to_csv(OBJECTIFS_CSV, index=False)

# --- Vérifications ---
def verifier_identifiants(username, password):
    users = st.session_state.users_df
    return not users[(users["username"] == username) & (users["password"] == password)].empty

def utilisateur_existe(username):
    return not st.session_state.users_df[st.session_state.users_df["username"] == username].empty

# --- Gestion des Utilisateurs ---
def ajouter_utilisateur(username, password):
    new_user = pd.DataFrame({"username": [username], "password": [password]})
    st.session_state.users_df = pd.concat([st.session_state.users_df, new_user], ignore_index=True)
    save_users()

# --- Gestion des Objectifs et Étapes ---
def ajouter_objectif(user, objectif):
    if user not in st.session_state.data:
        st.session_state.data[user] = {}
    if objectif not in st.session_state.data[user]:
        st.session_state.data[user][objectif] = []
    # On ne touche pas au CSV ici, le CSV sera mis à jour quand on ajoute des étapes
    # ou si vous le souhaitez, vous pouvez créer une ligne "objectif" vide. À vous de voir.

def ajouter_etape(user, objectif, etape_nom, etape_temps, etape_deadline, priorite):
    """
    1) Ajoute l’étape en mémoire (st.session_state.data).
    2) Ajoute l’étape dans le CSV objectifs_df.
    """
    # IMPORTANT: on ajoute check_in = "no" pour éviter le KeyError par la suite
    etape = {
        "Étape": etape_nom,
        "Temps (heures)": etape_temps,
        "Deadline": etape_deadline,
        "Priorité": priorite,
        "check_in": "no"  
    }

    # Mise à jour en mémoire
    if user not in st.session_state.data:
        st.session_state.data[user] = {}
    if objectif not in st.session_state.data[user]:
        st.session_state.data[user][objectif] = []
    st.session_state.data[user][objectif].append(etape)

    # Mise à jour dans le CSV
    ajouter_etape_csv(user, objectif, etape_nom, etape_temps, etape_deadline)

def ajouter_etape_csv(user, objectif, etape_nom, etape_temps, etape_deadline):
    new_row = pd.DataFrame({
        "user": [user],
        "objectif": [objectif],
        "etape_nom": [etape_nom],
        "etape_temps": [etape_temps],
        "etape_deadline": [etape_deadline],
        "check_in": ["no"]
    })
    st.session_state.objectifs_df = pd.concat([st.session_state.objectifs_df, new_row], ignore_index=True)
    save_objectifs()

def charger_data_depuis_csv(user):
    user_df = st.session_state.objectifs_df[st.session_state.objectifs_df["user"] == user]
    reconst_dict = {}
    for idx, row in user_df.iterrows():
        obj = row["objectif"]
        if obj not in reconst_dict:
            reconst_dict[obj] = []
        etape_info = {
            "Étape": row["etape_nom"],
            "Temps (heures)": row["etape_temps"],
            "Deadline": row["etape_deadline"],
            "Priorité": "-",  # vous pouvez gérer autrement
            "check_in": row.get("check_in", "no")
        }
        reconst_dict[obj].append(etape_info)

    if user not in st.session_state.data:
        st.session_state.data[user] = {}
    for obj_name, etapes_list in reconst_dict.items():
        if obj_name not in st.session_state.data[user]:
            st.session_state.data[user][obj_name] = []
        st.session_state.data[user][obj_name].extend(etapes_list)

# --- Génération du PDF ---
def generer_pdf(data, user):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Rapport - {user}", ln=True, align="C")
    pdf.ln(10)
    for objectif, etapes in data.items():
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 10, txt=f"Objectif: {objectif}", ln=True)
        pdf.ln(5)
        pdf.set_font("Arial", size=10)
        for etape in etapes:
            texte = (
                f"Étape: {etape['Étape']}, "
                f"Temps: {etape['Temps (heures)']}h, "
                f"Deadline: {etape['Deadline']}, "
                f"Priorité: {etape['Priorité']}, "
                f"Terminé ?: {etape.get('check_in', 'no')}"
            )
            pdf.multi_cell(0, 10, txt=texte)
            pdf.ln(2)
    filename = f"rapport_{user}.pdf"
    pdf.output(filename)
    st.success(f"Rapport généré : {filename}")
    with open(filename, "rb") as file:
        st.download_button(label="Télécharger le PDF", data=file, file_name=filename, mime="application/pdf")

# géneration des visuels
def afficher_bar_chart_temps_par_objectif(user):
    df_user = st.session_state.objectifs_df[st.session_state.objectifs_df["user"] == user]

    # Calculer les heures par objectif
    df_temps = df_user.groupby("objectif")["etape_temps"].sum().reset_index()

    chart = (
        alt.Chart(df_temps)
        .mark_bar()
        .encode(
            x=alt.X("objectif", sort="-y"),
            y="etape_temps",
            tooltip=["objectif", "etape_temps"]
        )
        .properties(title="Temps total par Objectif (heures)")
    )
    st.altair_chart(chart, use_container_width=True)

def afficher_pie_chart_progression(user):
    df_user = st.session_state.objectifs_df[st.session_state.objectifs_df["user"] == user]
    # Convertir check_in en “yes” ou “no” => 1 si yes, 0 sinon
    df_user["terminée"] = df_user["check_in"].apply(lambda x: 1 if x == "yes" else 0)

    termine = df_user["terminée"].sum()
    non_termine = len(df_user) - termine

    df_pie = pd.DataFrame({
        "Statut": ["Terminées", "Non terminées"],
        "Nb Étapes": [termine, non_termine]
    })

    fig = px.pie(df_pie, names="Statut", values="Nb Étapes", title="Progression des Étapes")
    st.plotly_chart(fig, use_container_width=True)


def afficher_gantt_chart(user):
    import plotly.figure_factory as ff

    # Filtrer les données pour l'utilisateur
    df_user = st.session_state.objectifs_df[st.session_state.objectifs_df["user"] == user].copy()

    # Vérification des données
    # st.write("Données après filtre :", df_user)

    # Forcer la conversion en datetime
    df_user["etape_deadline"] = pd.to_datetime(df_user["etape_deadline"], errors="coerce")

    # Supprimer les lignes avec des deadlines invalides
    if df_user["etape_deadline"].isnull().any():
        st.warning("Certaines deadlines sont invalides et seront ignorées.")
        df_user = df_user.dropna(subset=["etape_deadline"])

    # Ajouter une colonne "Start" (par exemple, quelques jours avant la deadline)
    df_user["Start"] = df_user["etape_deadline"] - pd.Timedelta(days=7)

    # Vérifier les colonnes nécessaires
    # st.write("Colonnes disponibles :", df_user.columns)

    # Construire les tâches pour le diagramme de Gantt
    tasks = []
    for idx, row in df_user.iterrows():
        tasks.append(dict(
            Task=row["objectif"],
            Start=row["Start"].strftime("%Y-%m-%d"),
            Finish=row["etape_deadline"].strftime("%Y-%m-%d"),
            Description=row["etape_nom"]
        ))

    # Vérifier qu'il y a des tâches
    if not tasks:
        st.info("Aucune tâche valide à afficher dans le diagramme de Gantt.")
        return

    # Créer le diagramme de Gantt
    fig = ff.create_gantt(
        tasks,
        index_col='Task',
        show_colorbar=True,
        showgrid_x=True,
        showgrid_y=True,
        title="Diagramme de Gantt des Objectifs"
    )
    st.plotly_chart(fig, use_container_width=True)




# --- Optimisation du temps (exemple) ---
def optimisation_repartition_ameliorée(user):
    objectifs_data = st.session_state.data.get(user, {})
    temps, priorites, deadlines, noms_etapes = [], [], [], []

    for objectif, etapes in objectifs_data.items():
        for etape in etapes:
            temps.append(etape["Temps (heures)"])
            priorites.append(etape["Priorité"])
            noms_etapes.append(etape["Étape"])
            # Deadline en jours
            delta = (pd.to_datetime(etape["Deadline"]).date() - datetime.date.today()).days
            deadlines.append(delta if delta > 0 else 0)

    if not temps:
        st.warning("Aucune donnée pour l'optimisation.")
        return

    heures_disponibles = st.number_input("Entrez le nombre d'heures disponibles :", min_value=1, step=1)
    if st.button("Lancer l'optimisation"):
        n = len(temps)
        c = np.array(temps) + 10*(np.array(priorites, dtype=int)-1)
        A_ub = np.ones((1, n))
        b_ub = np.array([heures_disponibles])

        for i in range(n):
            if deadlines[i] > 0:
                A_ub = np.vstack([A_ub, np.zeros(n)])
                A_ub[-1, i] = 1
                b_ub = np.append(b_ub, deadlines[i])

        bounds = [(0, temps[i]) for i in range(n)]
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
        if res.success:
            st.success("Optimisation terminée.")
            for i, temps_alloues in enumerate(res.x):
                st.write(f"Étape {noms_etapes[i]} : {temps_alloues:.2f} heures")
        else:
            st.error("L'optimisation a échoué.")

# --- Emploi du temps manuel ---
def afficher_emploi_du_temps(heure_debut=6, heure_fin=22, intervalle=2):
    jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]
    heures_disponibles = [f"{h}:00" for h in range(heure_debut, heure_fin + 1, intervalle)]
    emploi_du_temps = pd.DataFrame(index=heures_disponibles, columns=jours).fillna("Disponible")

    st.subheader(f"📅 Sélection des créneaux de {heure_debut}h à {heure_fin}h")
    if "emploi_du_temps" not in st.session_state:
        st.session_state.emploi_du_temps = emploi_du_temps

    for heure in heures_disponibles:
        cols = st.columns(len(jours))
        for idx, jour in enumerate(jours):
            if cols[idx].button(f"{jour} - {heure}", key=f"{jour}_{heure}"):
                if st.session_state.emploi_du_temps.at[heure, jour] == "Disponible":
                    st.session_state.emploi_du_temps.at[heure, jour] = "Réservé"
                else:
                    st.session_state.emploi_du_temps.at[heure, jour] = "Disponible"

    st.write(st.session_state.emploi_du_temps)
    return st.session_state.emploi_du_temps

def generer_emploi_du_temps(user):
    """Exemple: Allocation automatique par créneaux de 1h."""
    objectifs_data = st.session_state.data.get(user, {})
    etapes = []
    for objectif, steps in objectifs_data.items():
        for etape in steps:
            etapes.append({
                "Étape": etape["Étape"],
                "Temps (heures)": etape["Temps (heures)"],
                "Priorité": etape["Priorité"],
                "Deadline": etape["Deadline"]
            })

    if not etapes:
        st.warning("Aucune étape à répartir.")
        return

    etapes.sort(key=lambda x: x["Priorité"])  # Priorité croissante => 1 avant 5
    if "emploi_du_temps" not in st.session_state:
        st.warning("Aucun emploi du temps disponible.")
        return
    emploi_du_temps = st.session_state.emploi_du_temps

    # Convertir les créneaux disponibles en liste
    available_slots = []
    for index, row in emploi_du_temps.iterrows():
        for col in emploi_du_temps.columns:
            if row[col] == "Disponible":
                available_slots.append((index, col))

    emploi = emploi_du_temps.copy()
    for idx, row in emploi.iterrows():
        for col in emploi.columns:
            if emploi.at[idx, col] == "Réservé":
                # On ne touche pas les réservations
                pass
            else:
                emploi.at[idx, col] = "Disponible"

    for etape in etapes:
        temps_restants = etape["Temps (heures)"]
        for slot in available_slots:
            if temps_restants <= 0:
                break
            heure, jour = slot
            # Si ce slot est encore "Disponible"
            if emploi.at[heure, jour] == "Disponible":
                emploi.at[heure, jour] = etape["Étape"]
                temps_restants -= 1
                # On enlève ce slot de la liste
                available_slots.remove(slot)

    st.write("🗓 Emploi du Temps Alloué :")
    st.dataframe(emploi)
    return emploi


# --- Interface principale ---
def main():
    st.title("🎯 Suivi des Objectifs ")
    init_app()

    if st.session_state.current_user is None:
        login()
    else:
        st.success(f"Connecté en tant que : {st.session_state.current_user}")
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "Objectifs et Étapes",
            "Optimisation du Temps",
            "Créneau horaire",
            "Emploi du Temps",
            "Visualisation",
            "Rapport PDF"
        ])

        # 1) Objectifs / Étapes
        with tab1:
            st.sidebar.header("Ajouter un Objectif")
            objectif = st.sidebar.text_input("Nom de l'objectif")
            if st.sidebar.button("Créer l'objectif"):
                if objectif:
                    ajouter_objectif(st.session_state.current_user, objectif)
                    st.success(f"Objectif '{objectif}' créé avec succès.")
                else:
                    st.error("Le nom de l'objectif est requis.")

            st.sidebar.header("Ajouter des Étapes")
            list_objectifs = list(st.session_state.data.get(st.session_state.current_user, {}).keys())
            if list_objectifs:
                selected_objectif = st.sidebar.selectbox("Choisissez un objectif", list_objectifs)
                etape_nom = st.sidebar.text_input("Nom de l'étape")
                etape_temps = st.sidebar.number_input("Temps estimé (heures)", min_value=0.5, step=0.5)
                etape_deadline = st.sidebar.date_input("Deadline")
                etape_priorite = st.sidebar.number_input("Priorité (1 = élevée, 5 = faible)", min_value=1, max_value=5, value=3)

                if st.sidebar.button("Ajouter l'étape"):
                    if etape_nom:
                        ajouter_etape(
                            user=st.session_state.current_user,
                            objectif=selected_objectif,
                            etape_nom=etape_nom,
                            etape_temps=etape_temps,
                            etape_deadline=etape_deadline,
                            priorite=etape_priorite
                        )
                        st.success(f"Étape '{etape_nom}' ajoutée à l'objectif '{selected_objectif}'.")
                    else:
                        st.error("Le nom de l'étape est requis.")
            else:
                st.sidebar.info("Créez d'abord un objectif.")

            st.subheader("📋 Liste des Objectifs et Étapes")
            user_data = st.session_state.data.get(st.session_state.current_user, {})
            for obj, etapes in user_data.items():
                st.markdown(f"### {obj}")
                if etapes:
                    df = pd.DataFrame(etapes)

                    # On crée la colonne bool "Terminé ?" pour st.data_editor
                    df["Terminé ?"] = df["check_in"].apply(lambda x: True if x == "yes" else False)

                    # On affiche le data_editor
                    df_edit = st.data_editor(
                        df[["Étape", "Temps (heures)", "Deadline", "Priorité", "Terminé ?"]],
                        column_config={
                            "Terminé ?": st.column_config.CheckboxColumn(
                                label="Terminé ?",
                                help="Cochez si l'étape est terminée"
                            )
                        },
                        disabled=["Étape", "Temps (heures)", "Deadline", "Priorité"]
                    )

                    # Comparer l'ancien état et le nouvel état
                    for i in range(len(df_edit)):
                        new_val = "yes" if df_edit.loc[i, "Terminé ?"] else "no"
                        old_val = df.loc[i, "check_in"]
                        if new_val != old_val:
                            st.session_state.data[st.session_state.current_user][obj][i]["check_in"] = new_val
                            # Mettre à jour le CSV
                            etape_nom = df.loc[i, "Étape"]
                            idx_csv = st.session_state.objectifs_df[
                                (st.session_state.objectifs_df["user"] == st.session_state.current_user)
                                & (st.session_state.objectifs_df["objectif"] == obj)
                                & (st.session_state.objectifs_df["etape_nom"] == etape_nom)
                            ].index
                            if len(idx_csv) > 0:
                                st.session_state.objectifs_df.loc[idx_csv, "check_in"] = new_val
                                save_objectifs()
                else:
                    st.info("Aucune étape ajoutée.")

        # 2) Optimisation
        with tab2:
            st.subheader("⚙ Optimisation de la Répartition du Temps et des Ressources")
            optimisation_repartition_ameliorée(st.session_state.current_user)

        # 3) Créneaux
        with tab3:
            st.subheader("🗓 Sélection des créneaux horaires")
            heure_debut = st.slider("Heure de début", 6, 22, 6, 1)
            heure_fin = st.slider("Heure de fin", 6, 22, 22, 1)
            intervalle = st.slider("Intervalle (en heures)", 1, 3, 2, 1)
            afficher_emploi_du_temps(heure_debut, heure_fin, intervalle)

        # 4) Emploi du Temps auto
        with tab4:
            st.subheader("🗓 Répartition automatique des Étapes")
            if st.button("Répartir les étapes"):
                generer_emploi_du_temps(st.session_state.current_user)

        # 5) Visualisations
        with tab5:
            afficher_bar_chart_temps_par_objectif(st.session_state.current_user)
            afficher_pie_chart_progression(st.session_state.current_user)
            afficher_gantt_chart(st.session_state.current_user)
            
        # 6) PDF
        with tab6:
            if st.button("Exporter le rapport en PDF"):
                generer_pdf(user_data, st.session_state.current_user)

        # Bouton de déconnexion
            if st.sidebar.button("Se déconnecter"):
                st.session_state.current_user = None
                st.experimental_rerun()

# --- Interface de connexion ---
def login():
    st.subheader("🔐 Connexion ou Création de Compte")
    choix = st.radio("Choisissez une action :", ["Se connecter", "Créer un compte"])

    if choix == "Créer un compte":
        new_user = st.text_input("Nom d'utilisateur")
        new_password = st.text_input("Mot de passe", type="password")
        if st.button("Créer un compte"):
            if utilisateur_existe(new_user):
                st.error("Cet utilisateur existe déjà.")
            elif new_user and new_password:
                ajouter_utilisateur(new_user, new_password)
                st.success("Compte créé avec succès !")
            else:
                st.error("Veuillez remplir tous les champs.")
    else:  # "Se connecter"
        username = st.text_input("Nom d'utilisateur")
        password = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter"):
            if verifier_identifiants(username, password):
                st.session_state.current_user = username
                charger_data_depuis_csv(username)
                st.success(f"Connexion réussie ! Bienvenue, {username}.")
            else:
                st.error("Nom d'utilisateur ou mot de passe incorrect.")

# --- Lancement ---
if __name__ == "__main__":
    main()