import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options


def init_webdriver(browser):
    if browser == 'chrome':
        options = Options()
        options.headless = True # What does this do? 
        options.add_argument("--window-size=1920,1080")
        driver = webdriver.Chrome(options=options)
        print("driver is", driver)
        return driver
    # elif browser == 'firefox':
    #     return webdriver.Firefox('/path/to/geckodriver')
    # elif browser == 'safari':
    #     return webdriver.Safari()
    # elif browser == 'edge':
    #     return webdriver.Edge('/path/to/msedgedriver')
    else:
        raise ValueError(f'Unsupported browser: {browser}')

def test_click_button(browser):
    driver = init_webdriver(browser)
    print("browser is", browser)
    # driver.get('https://manage.get.gov')
    driver.get('https://bstackdemo.com/')
    print("driver.title is", driver.title)
    # print("browser.title", str(browser.title))

    # button = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'button_id')))
    # button = WebDriverWait(driver, 10).until(
    #     EC.element_to_be_clickable((By.CSS_SELECTOR, 'button'))
    # )
    # button.click()
    # driver.quit()

# Run the test with Chrome WebDriver
test_click_button('chrome')