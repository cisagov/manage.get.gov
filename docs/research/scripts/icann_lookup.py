"""
This script takes each domain in a dataset of non-.gov government domains and looks for 
which registrar they are currently registered with. 

This script can be run locally to generate data and currently takes some time to run.
"""

import csv
import requests
import whois

GOV_URLS_CSV_URL = "https://raw.githubusercontent.com/GSA/govt-urls/master/1_govt_urls_full.csv"

data = requests.get(GOV_URLS_CSV_URL).text
csv_data = list(csv.reader(data.splitlines(), delimiter=','))
domains = csv_data[1:]
fields = csv_data[0] + ['Registrar']

def check_registration(name):
    try:
        domain_info = whois.whois(name)
        return domain_info['registrar']
    except:
        print('Something went wrong')

full_data = []
for domain in domains:
    domain_name = domain[0].lower()
    if domain_name.endswith('.com') or domain_name.endswith('.edu') or domain_name.endswith('.net'):
        registrar = check_registration(domain_name)
        full_data.append(domain + [registrar])

with open('../data/registrar_data.csv', 'w') as f:
    writer = csv.writer(f)
    writer.writerow(fields)
    writer.writerows(full_data)
