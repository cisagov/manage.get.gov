import csv
import requests
import whois

GOV_URLS_CSV_URL = "https://raw.githubusercontent.com/GSA/govt-urls/master/1_govt_urls_full.csv"

data = requests.get(GOV_URLS_CSV_URL).text
csv_data = list(csv.reader(data.splitlines(), delimiter=','))
domains = csv_data[1:5]
fields = csv_data[0] + ['registrar']

def check_registration(name):
    domain_info = whois.whois(name)
    return domain_info['Registrar']

full_data = []
for domain in domains:
    domain_name = domain[0]
    registrar = check_registration(domain_name)
    full_data.append(domain + [registrar])

with open('../data/registrar_data.csv', 'w') as f:
    writer = csv.writer(f)
    writer.writerow(fields)
    writer.writerows(full_data)
