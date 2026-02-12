
# Paste the FULL dashboard code I gave you here
# ============================================================
# 🌊 RIVERATHON – AI Based Riparian Stress Dashboard
# Author: Kushagra Jha
# ============================================================


import streamlit as st
import ee
import geemap.foliumap as geemap
import datetime

# ------------------------------------------------------------
# PAGE CONFIG
# ------------------------------------------------------------
st.set_page_config(
    page_title="Riverathon Dashboard",
    layout="wide"
)

# ------------------------------------------------------------
# CUSTOM WATER WAVE BACKGROUND
# ------------------------------------------------------------
st.markdown("""
<style>
body {
    background: linear-gradient(to bottom, #e6f2ff, #ffffff);
}

.wave {
  position: fixed;
  bottom: 0;
  left: 0;
  width: 200%;
  height: 120px;
  background: url('https://i.imgur.com/ZAts69B.png') repeat-x;
  animation: wave 10s linear infinite;
  opacity: 0.4;
}

@keyframes wave {
  from {background-position: 0 0;}
  to {background-position: 1000px 0;}
}

.stButton>button {
    background-color:#003366;
    color:white;
    border-radius:5px;
}
</style>
<div class="wave"></div>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# SIMPLE LOGIN SYSTEM
# ------------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def login():
    st.title("🌊 Riverathon Login")

    user = st.text_input("Username")
    pwd = st.text_input("Password", type="password")

    if st.button("Login"):
        if user == "admin" and pwd == "riverathon":
            st.session_state.authenticated = True
        else:
            st.error("Invalid Credentials")

if not st.session_state.authenticated:
    login()
    st.stop()

# ------------------------------------------------------------
# INITIALIZE EARTH ENGINE
# ------------------------------------------------------------
ee.Initialize(project='ee-kushagrajha1111')

river = ee.FeatureCollection(
    'projects/ee-kushagrajha1111/assets/HARIDWAR_GANGES'
)

# ------------------------------------------------------------
# SIDEBAR CONTROLS
# ------------------------------------------------------------
st.sidebar.title("Controls")

months = [
'2024-01','2024-02','2024-03','2024-04',
'2024-05','2024-06','2024-07','2024-08',
'2024-09','2024-10','2024-11','2024-12'
]

selected_month = st.sidebar.selectbox("Select Month", months, index=9)

layer_type = st.sidebar.selectbox(
    "Select Layer",
    ['RVSI','CI','EVI','WBI','CHANGE']
)

# ------------------------------------------------------------
# IMAGE FUNCTIONS
# ------------------------------------------------------------
def getImage(start, end):
    col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
           .filterBounds(river)
           .filterDate(start, end)
           .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)))
    return col.median().clip(river)

def calculateAll(image):

    CI = image.select('B8').divide(image.select('B5')).subtract(1)
    EVI = image.expression(
        '2.5*((NIR-RED)/(NIR+6*RED-7.5*BLUE+1))',
        {
            'NIR': image.select('B8'),
            'RED': image.select('B4'),
            'BLUE': image.select('B2')
        }
    )

    WBI = image.select('B8').divide(image.select('B11'))

    waterStress = ee.Image(1).subtract(WBI.subtract(0.7).divide(0.5))
    chlStress = ee.Image(1).subtract(CI.subtract(1).divide(2))

    RVSI = waterStress.multiply(0.5)\
            .add(chlStress.multiply(0.5))\
            .clamp(0,1)

    return image.addBands([CI.rename('CI'),
                           EVI.rename('EVI'),
                           WBI.rename('WBI'),
                           RVSI.rename('RVSI')])

# ------------------------------------------------------------
# DATE HANDLING
# ------------------------------------------------------------
start_date_str = selected_month + "-01"
start_ee = ee.Date(start_date_str)

# Calculate end date (last day of the selected month)
end_ee = start_ee.advance(1, 'month').advance(-1, 'day')
end_date_str = end_ee.format('YYYY-MM-dd').getInfo()

current = calculateAll(getImage(start_date_str, end_date_str))

# Calculate previous month's start and end dates
prev_start_ee = start_ee.advance(-1, 'month')
prev_end_ee = start_ee.advance(-1, 'day')

prev_start_date_str = prev_start_ee.format('YYYY-MM-dd').getInfo()
prev_end_date_str = prev_end_ee.format('YYYY-MM-dd').getInfo()

previous = calculateAll(getImage(prev_start_date_str, prev_end_date_str))

# ------------------------------------------------------------
# MAP DISPLAY
# ------------------------------------------------------------
Map = geemap.Map(center=[29.9457, 78.1642], zoom=10)
Map.addLayer(river, {'color':'blue'}, 'River')

if layer_type == "RVSI":
    Map.addLayer(current.select('RVSI'),
                 {'min':0,'max':1,
                  'palette':['green','yellow','red']},
                 "RVSI")

elif layer_type == "CHANGE":
    change = current.select('RVSI')\
            .subtract(previous.select('RVSI'))
    Map.addLayer(change,
                 {'min':-0.3,'max':0.3,
                  'palette':['blue','white','red']},
                 "Change")

else:
    Map.addLayer(current.select(layer_type),
                 {'min':0,'max':1},
                 layer_type)

Map.to_streamlit(height=600)

# ------------------------------------------------------------
# STATISTICS PANEL
# ------------------------------------------------------------
st.subheader("📊 Statistics")

meanRVSI = current.select('RVSI')\
    .reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=river.geometry(),
        scale=10,
        maxPixels=1e13
    ).getInfo()['RVSI']

st.metric("Mean RVSI", round(meanRVSI,3))

# ------------------------------------------------------------
# ALERT SYSTEM
# ------------------------------------------------------------
if meanRVSI > 0.6:
    st.error("🚨 HIGH VEGETATION STRESS ALERT")
elif meanRVSI > 0.4:
    st.warning("⚠ Moderate Stress Observed")
else:
    st.success("✅ Vegetation Healthy")

# ------------------------------------------------------------
# EXPORT BUTTON
# ------------------------------------------------------------
if st.button("Export RVSI to Drive"):
    task = ee.batch.Export.image.toDrive(
        image=current.select('RVSI'),
        description=f'RVSI_{selected_month}',
        folder='Riverathon',
        region=river.geometry().bounds().getInfo()['coordinates'],
        scale=10,
        maxPixels=1e13
    )
    task.start()

    st.success("Export Task Started 🚀")
