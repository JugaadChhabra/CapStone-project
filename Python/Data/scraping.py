from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time

def scrape_oi_spurts_nse():
    url = "https://www.nseindia.com/market-data/oi-spurts"
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0.0.0")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 30)
    try:
        print(f"Opening {url} ...")
        driver.get(url)

        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table")))
        time.sleep(3)

        headers = [th.text.strip() for th in driver.find_elements(By.CSS_SELECTOR, "table thead tr th")]
        
        # Clean headers - remove empty ones and multi-line headers
        cleaned_headers = []
        for i, header in enumerate(headers):
            if header:  # If header is not empty
                # Clean multi-line headers
                cleaned_header = header.replace('\n', ' ').strip()
                cleaned_headers.append(cleaned_header)
            else:
                cleaned_headers.append(f"Col_{i}")  # Give empty headers a generic name
        
        print(f"Cleaned headers ({len(cleaned_headers)}): {cleaned_headers}")

        data = []
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        for row in rows:
            cells = [td.text.strip() for td in row.find_elements(By.TAG_NAME, "td")]
            if cells:
                while len(cells) < len(headers):
                    cells.append('')
                data.append(cells)

        if data:
            if len(cleaned_headers) > len(data[0]):
                cleaned_headers = cleaned_headers[:len(data[0])]
            elif len(cleaned_headers) < len(data[0]):
                cleaned_headers += [f"Extra_{i}" for i in range(len(data[0]) - len(cleaned_headers))]

        df = pd.DataFrame(data, columns=cleaned_headers)
        
        print(f"DataFrame shape: {df.shape}")
        print(f"Sample data:")
        print(df.head())

        # Clean numeric columns by removing commas and converting to numeric
        for col in df.columns:
            if df[col].dtype == 'object':  # Check if column contains string data
                df[col] = df[col].astype(str).str.replace(',', '', regex=False)
                df[col] = pd.to_numeric(df[col], errors='ignore')

        df.to_csv("oi_spurts_nse_clean.csv", index=False, encoding='utf-8-sig')
        print("Saved cleaned data to oi_spurts_nse_clean.csv")
    except Exception as e:
        print(f"Error while scraping: {e}")

    finally:
        driver.quit()

if __name__ == "__main__":
    scrape_oi_spurts_nse()
