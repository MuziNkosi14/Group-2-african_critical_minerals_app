import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from folium.plugins import MarkerCluster
from streamlit.components.v1 import html as components_html
import json, os
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# ---------------- config ----------------
st.set_page_config(page_title="African Critical Minerals", page_icon="🌍", layout="wide")
BASE = os.getcwd()
DATA_DIR = os.path.join(BASE, "data")
ASSETS_DIR = os.path.join(BASE, "assets")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

# Admin secret (local default)
ADMIN_SECRET = os.environ.get("ACM_ADMIN_SECRET", "letmein")

# ---------------- theme ----------------
st.markdown("""
<style>
body, .stApp {background:#071018;color:#e6eef2}
h1,h2,h3 {color:#4ee0d6}
.stSidebar {background:#0f1720}
footer {visibility:hidden}
</style>
""", unsafe_allow_html=True)

# ---------------- user helpers ----------------
def init_users():
    if not os.path.exists(USERS_FILE):
        admin = {
            "users": [
                {"id": 1, "username": "admin",
                 "password_hash": generate_password_hash("password"),
                 "role": "Administrator", "email": "admin@minerals.local",
                 "created_at": datetime.utcnow().isoformat()}
            ],
            "next_id": 2
        }
        with open(USERS_FILE, "w") as f:
            json.dump(admin, f, indent=2)

def load_users():
    init_users()
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(data):
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def create_user(username, password, role="Researcher", email=""):
    users = load_users()
    if not email:
        email = f"{username}@minerals.local"
    users["users"].append({
        "id": users["next_id"],
        "username": username,
        "password_hash": generate_password_hash(password),
        "role": role,
        "email": email,
        "created_at": datetime.utcnow().isoformat()
    })
    users["next_id"] += 1
    save_users(users)

def authenticate(login_id, password):
    users = load_users()
    for u in users["users"]:
        if (login_id == u["username"]) or (login_id == u.get("email")):
            if check_password_hash(u["password_hash"], password):
                return u
    return None

# ---------------- data loading ----------------
@st.cache_data
def load_data():
    def safe_read(name, cols=None):
        p = os.path.join(DATA_DIR, name)
        if os.path.exists(p):
            try:
                return pd.read_csv(p)
            except:
                return pd.DataFrame()
        return pd.DataFrame(columns=cols) if cols else pd.DataFrame()
    countries = safe_read("countries.csv", cols=["CountryID","CountryName","GDP_BillionUSD","MiningRevenue_BillionUSD","KeyProjects"])
    minerals = safe_read("minerals.csv", cols=["MineralID","MineralName","Description"])
    production = safe_read("production_stats.csv", cols=["CountryID","MineralID","Production_tonnes","ExportValue_BillionUSD"])
    sites = safe_read("sites.csv", cols=["SiteID","SiteName","CountryID","MineralID","Latitude","Longitude","Production_tonnes"])
    try:
        if not production.empty and not countries.empty and not minerals.empty:
            production = production.merge(countries, on="CountryID").merge(minerals, on="MineralID")
    except:
        pass
    try:
        if not sites.empty and not countries.empty and not minerals.empty:
            sites = sites.merge(countries, on="CountryID").merge(minerals, on="MineralID")
    except:
        pass
    return countries, minerals, production, sites

countries_df, minerals_df, production_df, sites_df = load_data()

# ---------------- safe rerun helper ----------------
def safe_rerun():
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    else:
        st.session_state["_refresh_flag"] = not st.session_state.get("_refresh_flag", False)
        st.stop()

# ---------------- logo finder ----------------
def find_logo():
    # Search assets folder for likely logo file names (case-insensitive)
    if not os.path.exists(ASSETS_DIR):
        return None
    candidates = []
    for fn in os.listdir(ASSETS_DIR):
        lower = fn.lower()
        if "logo" in lower or "african" in lower or "crit" in lower or "min" in lower:
            candidates.append(fn)
    # prefer exact expected name if present
    preferred = "african crit min logo.png"
    if preferred in os.listdir(ASSETS_DIR):
        return os.path.join(ASSETS_DIR, preferred)
    if candidates:
        # return first candidate (sorted for determinism)
        candidates.sort()
        return os.path.join(ASSETS_DIR, candidates[0])
    return None

# ---------------- map helper (returns folium.Map) ----------------
def build_map(df_sites, sel="All"):
    if df_sites.empty:
        return None
    df = df_sites if sel in (None, "All") else df_sites[df_sites["MineralName"] == sel]
    lat = pd.to_numeric(df["Latitude"], errors="coerce").mean() if "Latitude" in df.columns else 0
    lon = pd.to_numeric(df["Longitude"], errors="coerce").mean() if "Longitude" in df.columns else 0
    m = folium.Map(location=[lat or 0, lon or 0], zoom_start=3, tiles="CartoDB dark_matter", width="100%", height="100%")
    mc = MarkerCluster().add_to(m)
    minerals = df["MineralName"].dropna().unique().tolist()
    palette = px.colors.qualitative.Plotly
    cmap = {minerals[i]: palette[i % len(palette)] for i in range(len(minerals))}
    for _, r in df.iterrows():
        try:
            la = float(r["Latitude"]); lo = float(r["Longitude"])
        except Exception:
            continue
        popup = folium.Popup(f"<b>{r.get('SiteName','')}</b><br>Mineral: {r.get('MineralName','')}<br>Country: {r.get('CountryName','')}<br>Production: {int(r.get('Production_tonnes',0)):,} t", max_width=300)
        folium.CircleMarker(location=[la, lo], radius=6,
                            color=cmap.get(r.get("MineralName"), "#ffffff"),
                            fill=True, fill_opacity=0.9, popup=popup).add_to(mc)
    return m

# ---------------- auth UI ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "role" not in st.session_state:
    st.session_state.role = ""

def auth_section():
    logo_path = find_logo()
    if logo_path:
        try:
            st.sidebar.image(logo_path, width=160)
        except Exception:
            st.sidebar.title("🌍 African Critical Minerals")
    else:
        st.sidebar.title("🌍 African Critical Minerals")

    choice = st.sidebar.radio("Account", ["Login", "Register"])
    if choice == "Login":
        st.title("🔐 Login")
        login_id = st.text_input("Username or Email")
        pw = st.text_input("Password", type="password")
        if st.button("Login"):
            user = authenticate(login_id.strip(), pw)
            if user:
                st.session_state.logged_in = True
                st.session_state.username = user["username"]
                st.session_state.role = user["role"]
                safe_rerun()
            else:
                st.error("Invalid credentials")
    else:
        st.title("📝 Register")
        u = st.text_input("Username")
        email = st.text_input("Email (optional)")
        # allow Administrator option but require secret code
        role = st.selectbox("Role", ["Investor", "Researcher", "Administrator"])
        pw = st.text_input("Password", type="password")
        conf = st.text_input("Confirm Password", type="password")
        admin_code = ""
        if role == "Administrator":
            admin_code = st.text_input("Administrator code (required)", type="password")
        if st.button("Register"):
            if pw != conf:
                st.error("Passwords do not match.")
            elif not u or not pw:
                st.error("Provide username and password.")
            elif role == "Administrator" and admin_code != ADMIN_SECRET:
                st.error("Invalid administrator code. Contact the project owner.")
            else:
                users = load_users()
                if any(x["username"] == u for x in users["users"]):
                    st.error("Username already exists.")
                else:
                    create_user(u, pw, role=role, email=email.strip())
                    st.success("Registered — please log in.")
                    st.info("If you left email blank, we created username@minerals.local")

# ---------------- role views ----------------
def investor_view():
    st.header("Investor Dashboard")
    st.subheader("🏆 Top Performing Minerals")
    if not production_df.empty and "MineralName" in production_df.columns:
        top_m = production_df.groupby("MineralName")["Production_tonnes"].sum().sort_values(ascending=False).head(6)
        st.plotly_chart(px.bar(top_m.reset_index(), x="MineralName", y="Production_tonnes", title="Top Minerals"), use_container_width=True)
    else:
        st.info("No production data.")
    st.subheader("🌐 Top Performing Countries")
    if not production_df.empty and "CountryName" in production_df.columns:
        top_c = production_df.groupby("CountryName")["Production_tonnes"].sum().sort_values(ascending=False).head(6)
        st.plotly_chart(px.bar(top_c.reset_index(), x="CountryName", y="Production_tonnes", title="Top Countries"), use_container_width=True)
    else:
        st.info("No production data.")
    st.subheader("🗺️ Mining Sites (full width)")
    sel = st.selectbox("Mineral (optional)", ["All"] + minerals_df["MineralName"].dropna().unique().tolist(), key="inv_map_sel")
    fmap = build_map(sites_df, sel)
    if fmap:
        # render full HTML document from folium and embed
        components_html(fmap.get_root().render(), height=600)
    else:
        st.info("Sites data not available.")

def show_full_dashboard(readonly=True):
    st.subheader("Top Metrics")
    if not countries_df.empty:
        rev = countries_df["MiningRevenue_BillionUSD"].fillna(0).sum()
        gdp = countries_df["GDP_BillionUSD"].fillna(0).sum()
        st.metric("Total Mining Revenue (B USD)", f"${rev:,.1f}")
        st.metric("Total GDP (B USD)", f"${gdp:,.1f}")
    st.subheader("Top Performing Minerals")
    if not production_df.empty and "MineralName" in production_df.columns:
        top_m = production_df.groupby("MineralName")["Production_tonnes"].sum().sort_values(ascending=False).head(8)
        st.plotly_chart(px.bar(top_m.reset_index(), x="MineralName", y="Production_tonnes"), use_container_width=True)
    st.subheader("Map & Sites (full width)")
    sel = st.selectbox("Mineral", ["All"] + minerals_df["MineralName"].dropna().unique().tolist(), key="full_map_sel")
    fmap = build_map(sites_df, sel)
    if fmap:
        components_html(fmap.get_root().render(), height=600)
    else:
        st.info("No sites loaded.")
    st.subheader("Country Profile")
    country_list = countries_df["CountryName"].tolist() if not countries_df.empty else []
    country = st.selectbox("Country", country_list, key="country_sel")
    if country:
        row = countries_df[countries_df["CountryName"] == country].iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("GDP (B USD)", f"${row.get('GDP_BillionUSD',0):,.1f}")
        c2.metric("Mining Rev (B USD)", f"${row.get('MiningRevenue_BillionUSD',0):,.1f}")
        c3.metric("Mining % GDP", f"{(row.get('MiningRevenue_BillionUSD',0)/row.get('GDP_BillionUSD',1))*100:.2f}%")
        st.markdown(f"**Key Projects:** {row.get('KeyProjects','N/A')}")
        if not production_df.empty:
            prod = production_df[production_df["CountryName"] == country]
            if not prod.empty:
                fig = px.bar(prod, x="MineralName", y="Production_tonnes", color="MineralName", title=f"{country} - Production")
                st.plotly_chart(fig, use_container_width=True)
    st.subheader("Compare Countries")
    mult = st.multiselect("Choose countries", country_list, default=country_list[:2] if country_list else [])
    if mult and not production_df.empty:
        comp = production_df[production_df["CountryName"].isin(mult)]
        if not comp.empty:
            fig2 = px.bar(comp, x="MineralName", y="Production_tonnes", color="CountryName", barmode="group")
            st.plotly_chart(fig2, use_container_width=True)

def admin_view():
    st.header("Administrator Dashboard")
    show_full_dashboard(readonly=False)
    st.markdown("---")
    st.subheader("Import CSV (admin)")
    uploaded = st.file_uploader("Upload CSV (must be named exactly countries.csv, minerals.csv, production_stats.csv or sites.csv)", type=["csv"])
    if uploaded:
        fname = uploaded.name
        if fname in ["countries.csv","minerals.csv","production_stats.csv","sites.csv"]:
            with open(os.path.join(DATA_DIR, fname), "wb") as f:
                f.write(uploaded.getbuffer())
            st.success(f"Saved {fname}. Reloading data...")
            st.cache_data.clear()
            global countries_df, minerals_df, production_df, sites_df
            countries_df, minerals_df, production_df, sites_df = load_data()
            safe_rerun()
        else:
            st.error("Use exact filenames: countries.csv, minerals.csv, production_stats.csv, sites.csv")

    st.subheader("Manage Users")
    users = load_users()
    dfu = pd.DataFrame(users["users"])
    if not dfu.empty:
        st.dataframe(dfu[["id","username","role","email","created_at"]])
        uid = st.number_input("User ID to delete", min_value=2, step=1)
        if st.button("Delete User"):
            users["users"] = [u for u in users["users"] if u["id"] != int(uid)]
            save_users(users)
            st.success("User deleted.")
            safe_rerun()

def researcher_view():
    st.header("Researcher View (read-only)")
    show_full_dashboard(readonly=True)

# ---------------- main ----------------
def main():
    if not st.session_state.logged_in:
        auth_section()
        return

    st.sidebar.success(f"{st.session_state.username} ({st.session_state.role})")
    if st.sidebar.button("Logout"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        safe_rerun()

    role = st.session_state.role
    pages = []
    if role == "Investor":
        pages = ["Investor"]
    elif role == "Researcher":
        pages = ["Researcher", "Home"]
    elif role == "Administrator":
        pages = ["Admin", "Home"]
    else:
        pages = ["Home"]
    page = st.sidebar.selectbox("Page", pages)

    if page == "Investor":
        investor_view()
    elif page == "Researcher":
        researcher_view()
    elif page == "Admin":
        admin_view()
    else:
        if role == "Administrator":
            admin_view()
        elif role == "Researcher":
            researcher_view()
        else:
            investor_view()

if __name__ == "__main__":
    init_users()
    countries_df, minerals_df, production_df, sites_df = load_data()
    main()
