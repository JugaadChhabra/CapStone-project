from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time

def scrape_for_oi():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)

    driver.get("https://smartoptions.trendlyne.com/futures/oi-gainers/")

    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table")))
        
        headers = [th.text.strip() for th in driver.find_elements(By.CSS_SELECTOR, "table th")]
        rows = driver.find_elements(By.CSS_SELECTOR, "table tr")
        
        data = []
        for row in rows[1:]:
            cells = [cell.text.strip() for cell in row.find_elements(By.TAG_NAME, "td")]
            if cells:
                data.append(cells)
        
        df = pd.DataFrame(data, columns=headers)
        
        print(df.head())
        
        df.to_csv("oi_gainers_trendlyne.csv", index=False)
        print("Saved as oi_gainers_trendlyne.csv")

    except Exception as e:
        print(f"Failed to load or scrape data: {e}")

    finally:
        driver.quit()