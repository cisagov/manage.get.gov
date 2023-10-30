## Purpose
Use this folder for storing files for the migration process. Should otherwise be empty on local dev environments unless necessary. This folder must exist due to the nature of how data is stored on cloud.gov and the nature of the data we typically want to send. 

## How do I migrate registrar data? 
This process is detailed in [data_migration.md](../../docs/operations/data_migration.md)

## What kind of files can I store here?
The intent is for PII data or otherwise, but this can exist in any format. Do note that the data contained in this file will be temporary, so after the app is restaged it will lose it (as long as nothing is committed). This is ideal for migration files as they write to our DB, but not for something you need to permanently hold onto.