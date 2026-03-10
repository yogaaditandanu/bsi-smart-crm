import streamlit as st
import pandas as pd
import plotly.express as px

# ==========================================
# 1. KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(page_title="BSI Smart CRM", page_icon="📈", layout="wide")

# ==========================================
# 2. FUNGSI LOAD DATA & ALGORITMA (ALL-IN-ONE)
# ==========================================
@st.cache_data
def load_and_process_data():
    try:
        # 1. Baca data mentah langsung (Pastikan nama file sesuai dengan yang ada di foldermu)
        df_chat = pd.read_excel("Data_BSI_Kategori_Baru_Final_Dipisah.xlsx")
        df_pers = pd.read_excel("data_personalization_100326 1.xlsx")
        
        # 2. Gabungkan Data
        df = pd.merge(
            df_chat[['timestamp', 'user id', 'user input', 'kategori_baru']], 
            df_pers.drop(columns=['user input', 'predicted category'], errors='ignore'),
            on=['timestamp', 'user id'], 
            how='left'
        ).drop_duplicates(subset=['timestamp', 'user id']).reset_index(drop=True)

        # 3. Algoritma Dynamic Scoring (Menentukan Rank Otomatis)
        kategori_stats = df.groupby('kategori_baru').agg(volume=('user id', 'count'), avg_saldo=('saldoavg', 'mean')).reset_index()
        kategori_stats['skor_popularitas'] = kategori_stats['volume'] / kategori_stats['volume'].max()
        kategori_stats['skor_kekayaan'] = kategori_stats['avg_saldo'] / kategori_stats['avg_saldo'].max()
        
        margin_multiplier = {
            'CICIL_EMAS': 5.0, 'PEMBIAYAAN': 5.0, 'GADAI_EMAS': 4.0, 'TABUNG_EMAS': 3.0, 
            'KUR': 3.0, 'HAJI': 2.0, 'UMROH': 2.0, 'TABUNGAN': 1.5, 'DEPOSITO': 1.0, 'INFO_EMAS': 0.5
        }
        kategori_stats['multiplier'] = kategori_stats['kategori_baru'].map(margin_multiplier).fillna(1.0)
        kategori_stats['FINAL_SCORE'] = (kategori_stats['skor_popularitas'] + kategori_stats['skor_kekayaan']) * kategori_stats['multiplier']
        kategori_stats = kategori_stats.sort_values(by='FINAL_SCORE', ascending=False).reset_index(drop=True)
        kategori_stats['Priority_Rank'] = kategori_stats.index + 1
        
        df = pd.merge(df, kategori_stats[['kategori_baru', 'Priority_Rank']], on='kategori_baru', how='left').fillna({'Priority_Rank': 99})

        # 4. Engine Action Tag & WA Drafter
        def generate_crm_content(row):
            kategori = str(row['kategori_baru']).replace("_", " ")
            saldo = row['saldoavg']
            rfm = str(row['rfm_segment'])
            gen = str(row['generation'])
            job = str(row.get('job', 'Bapak/Ibu'))
            saldo_str = f"Rp {saldo:,.0f}" if pd.notna(saldo) else "Rp -"
            rank = row['Priority_Rank']

            # A. Action Tag untuk Sales
            action = f"Tindak lanjut standar untuk {kategori}."
            if rank == 1: action = f"🔥 TOP PRIORITAS 1! Nasabah {rfm}. Saldo avg {saldo_str}. Konversi segera: {kategori}."
            elif rank == 2: action = f"⚡ PRIORITAS 2! Prospek kuat. Profil: {job}. Fokuskan penawaran pada {kategori}."
            elif rank in [3, 4, 5]: action = f"💰 PRIORITAS {int(rank)} (Menengah). Nasabah {rfm}. Saldo: {saldo_str}. Tawarkan {kategori}."
            elif row['kategori_baru'] == 'INFO_EMAS': action = "ℹ️ LOW PRIORITY: Cukup berikan edukasi harga emas hari ini."

            # B. AI WA Drafter (Template pesan siap kirim)
            sapaan = "Kak" if gen in ['Gen Z', 'Millenials'] else "Bapak/Ibu"
            if rank <= 2:
                wa_draft = f"Assalamu'alaikum {sapaan}. Sebagai nasabah prioritas BSI ({rfm}), kami melihat {sapaan} memiliki minat pada {kategori}. Kami memiliki penawaran margin spesial khusus hari ini. Apakah berkenan kami telepon sebentar?"
            elif row['kategori_baru'] == 'TABUNG_EMAS':
                wa_draft = f"Assalamu'alaikum {sapaan}. Terima kasih telah menghubungi BSI! Untuk mulai berinvestasi Tabungan Emas sangat mudah, cukup buka aplikasi BYOND dan mulai dari Rp50.000 saja. Ada yang bisa kami bantu arahkan?"
            else:
                wa_draft = f"Assalamu'alaikum {sapaan}. Terima kasih atas ketertarikannya pada layanan {kategori} BSI. Berikut adalah informasi yang {sapaan} butuhkan..."

            return pd.Series([action, wa_draft, saldo_str])

        df[['Action_Tag_Hyper', 'Draft_WA_AI', 'Saldo_Rupiah']] = df.apply(generate_crm_content, axis=1)
        
        # Tambahkan Status Tracker Dummy
        df['Status_FollowUp'] = '🔴 Baru Masuk'
        
        return df.sort_values(by=['Priority_Rank', 'saldoavg'], ascending=[True, False]).reset_index(drop=True)
    except Exception as e:
        st.error(f"⚠️ Terjadi kesalahan saat membaca data: {e}")
        return pd.DataFrame()

df = load_and_process_data()

if not df.empty:
    # ==========================================
    # 3. SIDEBAR (FILTER INTERAKTIF)
    # ==========================================
    st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/a/a0/Bank_Syariah_Indonesia.svg/1200px-Bank_Syariah_Indonesia.svg.png", width=150)
    st.sidebar.title("🔍 Filter Prospek")
    
    kategori_filter = st.sidebar.multiselect("Kategori Produk:", options=df['kategori_baru'].unique(), default=df['kategori_baru'].unique())
    rfm_options = [x for x in df['rfm_segment'].unique() if pd.notna(x)]
    rfm_filter = st.sidebar.multiselect("Segmen Nasabah (RFM):", options=rfm_options, default=rfm_options)

    df_filtered = df[(df['kategori_baru'].isin(kategori_filter)) & (df['rfm_segment'].isin(rfm_filter))]

    # ==========================================
    # 4. HEADER & KPI METRICS
    # ==========================================
    st.title("📈 BSI Smart CRM - Algorithmic Hyperpersonalization")
    st.markdown("Dilengkapi dengan **Market Insights** dan **AI WhatsApp Drafter** untuk efisiensi tim Sales.")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Leads (Chat)", len(df_filtered))
    col2.metric("🔥 Top Priority Leads", len(df_filtered[df_filtered['Priority_Rank'] <= 3]))
    
    avg_saldo = df_filtered['saldoavg'].mean()
    col3.metric("💰 Rata-rata Saldo Leads", f"Rp {avg_saldo/1000000:.1f} Juta" if pd.notna(avg_saldo) else "Rp 0")
    col4.metric("🏆 Nasabah Champion/Promising", len(df_filtered[df_filtered['rfm_segment'].isin(['CHAMPION', 'PROMISING'])]))

    st.divider()

    # ==========================================
    # 5. DEMOGRAFI & MARKET INSIGHTS (FITUR BARU)
    # ==========================================
    st.subheader("👥 Demografi & Market Insights (Berdasarkan Filter)")
    col_demo1, col_demo2 = st.columns(2)
    
    with col_demo1:
        # Pie Chart Generasi (Gen Z, Millenials, dll)
        fig_gen = px.pie(df_filtered, names='generation', title="Distribusi Generasi Nasabah", hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_gen, use_container_width=True)
        
    with col_demo2:
        # Pie Chart Profesi Nasabah
        fig_job = px.pie(df_filtered, names='job', title="Distribusi Profesi Nasabah", hole=0.4, color_discrete_sequence=px.colors.qualitative.Set3)
        st.plotly_chart(fig_job, use_container_width=True)

    st.divider()

    # ==========================================
    # 6. VISUALISASI VOLUME CHART (TREEMAP & BAR)
    # ==========================================
    st.subheader("📊 Analisis Volume & Prioritas Leads")
    chart_data = df_filtered.groupby(['kategori_baru', 'Priority_Rank']).size().reset_index(name='Jumlah Chat')
    
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        fig_tree = px.treemap(chart_data, path=['kategori_baru'], values='Jumlah Chat', color='Priority_Rank', color_continuous_scale='Reds_r', title="🎯 Peta Prioritas & Volume")
        fig_tree.update_traces(textinfo="label+value", textfont_size=14)
        st.plotly_chart(fig_tree, use_container_width=True)

    with col_chart2:
        chart_data_sorted = chart_data.sort_values('Jumlah Chat', ascending=True)
        fig_bar = px.bar(chart_data_sorted, x='Jumlah Chat', y='kategori_baru', text='Jumlah Chat', orientation='h', color='Priority_Rank', color_continuous_scale='Reds_r', title="📈 Volume Leads Terbanyak")
        fig_bar.update_traces(textposition='outside')
        fig_bar.update_layout(coloraxis_showscale=False) 
        st.plotly_chart(fig_bar, use_container_width=True)

    st.divider()

    # ==========================================
    # 7. TABEL CRM UTAMA (DENGAN WA DRAFTER)
    # ==========================================
    st.subheader("📋 Actionable Leads & AI Drafter (Siap Eksekusi)")
    st.markdown("Tim Sales tidak perlu memikirkan kata-kata lagi. Tinggal *copy-paste* teks di kolom **Draft_WA_AI** dan kirim ke nasabah!")
    
    display_cols = ['Status_FollowUp', 'Priority_Rank', 'kategori_baru', 'Action_Tag_Hyper', 'Draft_WA_AI', 'user id', 'Saldo_Rupiah', 'rfm_segment', 'generation']
    
    st.dataframe(
        df_filtered[display_cols].style.background_gradient(subset=['Priority_Rank'], cmap='Greens_r'), 
        height=600, 
        use_container_width=True
    )