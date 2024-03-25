import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options


def init_webdriver(browser):
    if browser == 'chrome':
        options = Options()
        options.headless = True
        options.add_argument("--window-size=1920,1080")
        driver = webdriver.Chrome(options=options)
        print("!! driver is", driver)
        return driver
        # webdriver_path = os.path.abspath("webdrivers/chromedriver_mac_arm64/chromedriver.exe")
        # print("!! webdriver path is ", webdriver_path)
        # return webdriver.Chrome(executable_path=webdriver_path)
        # driver = webdriver.Chrome(executable_path=webdriver_path)
        # print("!! driver is", driver)
        # Initialize WebDriver with the absolute path
        # driver = webdriver.Chrome(webdriver_path)
        # print("!!", driver) 
        # return webdriver.Chrome('webdrivers/chromedriver_mac_arm64/chromedriver.exe')
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
    print("!! browser is", browser)
    print("!! driver is", driver)
    # driver.get('https://manage.get.gov')
    driver.get('https://bstackdemo.com/')
    print("browser.title", browser.title)
    # button = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'button_id')))
    # button = WebDriverWait(driver, 10).until(
    #     EC.element_to_be_clickable((By.CSS_SELECTOR, 'button'))
    # )
    # button.click()
    # driver.quit()

# Run the test with Chrome WebDriver
test_click_button('chrome')