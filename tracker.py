import pandas as pd
import time
import os
import re
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ===== FILE PATHS =====
INPUT_FILE = "dataset/state_cities.csv"
OUTPUT_FILE = "new_data.csv"

# ===== Helper: Normalize City Names =====
def normalize_city(city):
    return str(city).strip().lower()

# ===== Load Cities =====
cities_df = pd.read_csv(INPUT_FILE)
cities = cities_df.iloc[:, 1].dropna().astype(str).tolist()
cities_norm = [normalize_city(c) for c in cities]

# ===== Force Start From City  =====
start_index = 3400
print(f"🚀 Starting from city index {start_index} ({cities[start_index]})")

# ===== Resume Support: Already Scraped Cities =====
done_cities = set()
if os.path.exists(OUTPUT_FILE):
    try:
        existing = pd.read_csv(OUTPUT_FILE, encoding="utf-8")
        if "city" in existing.columns:
            done_cities = set(existing["city"].dropna().astype(str).map(normalize_city).unique().tolist())
        print(f"✅ Found {len(done_cities)} cities already scraped")
    except Exception as e:
        print(f"⚠️ Could not read output file: {e}")

# ===== Selenium Setup =====
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)

# ===== Ensure CSV Exists with Header =====
file_exists = os.path.exists(OUTPUT_FILE)
csv_file = open(OUTPUT_FILE, "a", newline="", encoding="utf-8")
writer = csv.writer(csv_file)

if not file_exists:
    writer.writerow(["title", "street", "city", "state", "zipcode", "phone", "email"])
    csv_file.flush()
    os.fsync(csv_file.fileno())

# ===== Helper: Clean Phone =====
def clean_phone(phone):
    return re.sub(r"\D", "", phone) if phone else ""

# ===== Helper: Scroll page until all cards load =====
def scroll_to_bottom():
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

# ===== Scraper Function =====
def scrape_city(city, writer, csv_file):
    print(f"\n🔍 Searching for: {city}")
    driver.get("https://www.selfstoragetracker.com/")

    # Search box
    try:
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ctl00_txtsearch"))
        )
        search_box.clear()
        search_box.send_keys(city)
        search_box.send_keys(Keys.RETURN)
        time.sleep(3)
    except Exception as e:
        print(f"❌ Failed search for {city}: {e}")
        return False

    # Ensure full page loads
    scroll_to_bottom()

    # Get all cards
    try:
        cards = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".fleamarketrow.shadow.border"))
        )
    except:
        print(f"⚠️ No results for {city}")
        return False

    count = 0
    for idx, card in enumerate(cards, 1):
        try:
            title = card.find_element(By.CSS_SELECTOR, ".row.mb-3").text.strip()
        except:
            title = ""

        try:
            street = card.find_element(By.XPATH, ".//span[contains(@id,'ADDRESS1')]").text.strip()
        except:
            street = ""

        try:
            city_name = card.find_element(By.XPATH, ".//span[contains(@id,'CITY')]").text.strip()
        except:
            city_name = city

        try:
            state = card.find_element(By.XPATH, ".//span[contains(@id,'STATE')]").text.strip()
        except:
            state = ""

        try:
            zipcode = card.find_element(By.XPATH, ".//span[contains(@id,'Label3')]").text.strip()
        except:
            zipcode = ""

        try:
            phone_elem = card.find_element(By.XPATH, ".//span[contains(@id,'MERCHANDISE')]")
            phone = clean_phone(phone_elem.text.strip())
        except:
            phone = ""

        try:
            email_elem = card.find_element(By.XPATH, ".//span[contains(@id,'Label1')]")
            email = email_elem.text.strip()
        except:
            email = ""

        row = [title, street, city_name, state, zipcode, phone, email]

        if not all([title, street, city_name, state, zipcode]):
            print(f"⏭️ Skipping incomplete row: {row}")
            continue

        writer.writerow(row)
        csv_file.flush()             # flush python buffer
        os.fsync(csv_file.fileno())  # flush OS buffer
        count += 1
        print(f"{idx}. {row}")

    if count > 0:
        print(f"✅ Saved {count} records for {city}")
        return True
    else:
        print(f"⚠️ No complete records found for {city}")
        return False

# ===== Main Loop =====
for i in range(start_index, len(cities)):
    city = cities[i]
    city_norm = cities_norm[i]

    if city_norm in done_cities:
        print(f"⏭️ Skipping {city} (already done)")
        continue

    scrape_city(city, writer, csv_file)

# ===== Cleanup =====
csv_file.close()
driver.quit()
print("🎉 Scraping completed!")
