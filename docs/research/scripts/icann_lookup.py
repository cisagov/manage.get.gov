#!/usr/bin/env python3

"""
This script takes each domain in a dataset of non-.gov government domains and looks for 
which registrar they are currently registered with. 

This script can be run locally to generate data and currently takes some time to run.

NOTE: This requries python-whois and argparse to be installed. 
"""

import csv
import requests
import whois  # this is python-whois
import argparse
import sys
from pathlib import Path

GOV_URLS_CSV_URL = (
    "https://raw.githubusercontent.com/GSA/govt-urls/master/1_govt_urls_full.csv"
)

data = requests.get(GOV_URLS_CSV_URL).text
csv_data = list(csv.reader(data.splitlines(), delimiter=","))
domains = csv_data[1:]
fields = csv_data[0] + ["Registrar"]


def check_registration(name):
    try:
        domain_info = whois.whois(name)
        return domain_info["registrar"]
    except KeyboardInterrupt:
        sys.exit(1)
    except:
        print(f"Something went wrong with that domain lookup for {name}, continuing...")


def main(domain):
    full_data = []
    if domain:
        registrar = check_registration(domain)
        print(registrar)
    else:
        for idx, domain in enumerate(domains):
            domain_name = domain[0].lower()
            if (
                domain_name.endswith(".com")
                or domain_name.endswith(".edu")
                or domain_name.endswith(".net")
            ):
                print(idx)
                print(domain_name)
                registrar = check_registration(domain_name)
                full_data.append(domain + [registrar])

    Path("../data").mkdir(exist_ok=True)

    with open("../data/registrar_data.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        writer.writerows(full_data)


if __name__ == "__main__":
    cl = argparse.ArgumentParser(description="This performs ICANN lookups on domains.")
    cl.add_argument(
        "--domain", help="finds the registrar for a single domain", default=None
    )
    args = cl.parse_args()

    sys.exit(main(args.domain))
