# Django admin user roles

Roles other than superuser should be defined in authentication and authorization groups in django admin 

## Superuser

Full access

## CISA analyst

### Basic permission level

Staff

### Additional group permissions

auditlog | log entry | can view log entry
registrar | contact | can view contact
registrar | domain application | can change domain application
registrar | domain | can view domain
registrar | user | can view user