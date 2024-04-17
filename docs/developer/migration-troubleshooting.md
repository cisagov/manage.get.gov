## Troubleshooting

### Your toolkit
For a general overview, read [this documentation](https://www.algotech.solutions/blog/python/django-migrations-and-how-to-manage-conflicts/)


Some common commands:
- docker-compose exec app bash -- gets you into bash
- ./manage.py showmigrations -- shows the current migrations that are finished, all should have [x]
- ./manage.py makemigrations -- makes the migration
- ./manage.py showmigrations -- now you should see the new/updated migration with a [ ]
- ./manage.py migrate [folder name here, ie registrar] -- applies those changes to db for specific folder
- ./manage.py showmigrations -- the migration changes should now have a [x] by it


## Scenarios

### Scenario 1: Conflicting migrations on local

If you get conflicting migrations on local, you probably have a new migration on your branch and you merged main which had new migrations as well. Do NOT merge migrations together. 

Assuming your local migration is `40_local_migration` and the migration from main is `40_some_migration_from_main`:
- Delete `40_local_migration`
- Run `docker-compose exec app ./manage.py makemigrations`
- Run `docker-compose down`
- Run `docker-compose up` 
- Run `docker-compose exec app ./manage.py migrate`

You should end up with `40_some_migration_from_main`, `41_local_migration`

Alternatively, assuming that the conflicting migrations are not dependent on each other, you can manually edit the migration file such that your new migration is incremented by one (file name, and definition inside the file) but this approach is not recommended.

### Scenario 2: Conflicting migrations on sandbox

This occurs when the logs return the following:
>Conflicting migrations detected; multiple leaf nodes in the migration graph: (0040_example, 0041_example in base).
To fix them run 'python manage.py makemigrations --merge'

This happens when you swap branches on your sandbox that contain diverging leaves (eg: 0040_example, 0041_example). The fix is to go into the sandbox, delete one of these leaves, fake run the preceding migration, hand run the remaining previously conflicting leaf, fake run the last migration:

- `cf login -a api.fr.cloud.gov --sso`
- `cf ssh getgov-<app>`
- `/tmp/lifecycle/shell`
- Find the conflicting migrations:  `./manage.py showmigrations`
- Delete one of them: `rm registrar/migrations/0041_example.py`
- `/manage.py showmigrations`
- `/manage.py makemigrations`
- `/manage.py migrate`

### Scenario 3: Migrations ran incorrectly, and migrate no longer works (sandbox)

This has happened when updating user perms (so running a new data migration). Something is off with the update on the sandbox and you need to run that last data migration again:
- `cf login -a api.fr.cloud.gov --sso`
- `cf run-task getgov-<app> --wait --command 'python manage.py migrate registrar 39_penultimate_miration --fake' --name migrate`
- `cf run-task getgov-<app> --wait --command 'python manage.py migrate' --name migrate`

### Scenario 4: All migrations refuse to load due to existing duplicates on sandboxes

This typically happens with a DB conflict that prevents 001_initial from loading. For instance, let's say all migrations have ran successfully before, and a zero command is ran to reset everything. This can lead to a catastrophic issue with your postgres database.

To diagnose this issue, you will have to manually delete tables using the psql shell environment. If you are in a production environment and cannot lose that data, then you will need some method of backing that up and reattaching it to the table.

1. `cf login -a api.fr.cloud.gov --sso`
2. Run `cf connect-to-service -no-client getgov-{environment_name} getgov-{environment_name}-database` to open a SSH tunnel
3. Run `psql -h localhost -p {port} -U {username} -d {broker_name}`
4. Open a new terminal window and run `cf ssh getgov-{environment_name}`
5. Within that window, run `tmp/lifecycle/shell`
6. Within that window, run `./manage.py migrate` and observe which tables are duplicates

Afterwards, go back to your psql instance. Run the following for each problematic table:

7. `DROP TABLE {table_name} CASCADE` 

**WARNING:** this will permanently erase data! Be careful when doing this and exercise common sense.

Then, run `./manage.py migrate` again and repeat step 7 for each table which returns this error.
After these errors are resolved, follow instructions in the other scenarios if applicable.   

### Scenario 5: Permissions group exist, but my users cannot log onto the sandbox

This is most likely due to fixtures not running or fixtures running before the data creating migration. Simple run fixtures again (WARNING: This applies to dev sandboxes only. We never want to rerun fixtures on a stable environment)

- `cf login -a api.fr.cloud.gov --sso`
- `cf run-task getgov-<app> --command "./manage.py load" --name fixtures` 

### Scenario 6: Data is corrupted on the sandbox

Example: there are extra columns created on a table by an old migration long since gone from the code. In that case, you may have to tunnel into your DB on the sandbox and hand-delete these columns. See scenario #4 if you are running into duplicate table definitions. Also see [this documentation](docs/developer/database-access.md) for a good reference here:

- `cf login -a api.fr.cloud.gov --sso`
- Open a new terminal window and run `cf ssh getgov{environment_name}`
- Run `tmp/lifecycle/shell`
- Run `./manage.py migrate` and observe which tables have invalid column definitions
- Run the `\l` command to see all of the databases that are present
- `\c cgawsbrokerprodlgi635s6c0afp8w` (assume cgawsbrokerprodlgi635s6c0afp8w is your DB)
‘\dt’ to see the tables
- `SELECT * FROM {bad_table};`
- `alter table registrar_domain drop {bad_column};`

### Scenario 7: Continual 500 error for the registrar + your requests (login, clicking around, etc) are not showing up in the logstream

Example: You are able to log in and access the /admin page, but when you arrive at the registrar you keep getting 500 errors and your log-ins any API calls you make via the UI does not show up in the log stream. And you feel like you’re starting to lose your marbles.

In the CLI, run the command `cf routes`
If you notice that your route of `getgov-<app>.app.cloud.gov` is pointing two apps, then that is probably the major issue of the 500 error. (ie mine was pointing at `getgov-<app>.app.cloud.gov` AND `cisa-dotgov`)
In the CLI, run the command `cf apps` to check that it has an app running called `cisa-dotgov`. If so, there’s the error!
Essentially this shows that your requests were being handled by two completely separate applications and that’s why some requests aren’t being located. 
To resolve this issue, remove the app named `cisa-dotgov` from this space.
Test out the sandbox from there and it should be working!

**Debug connectivity**

dig https://getgov-<app>.app.cloud.gov (domain information groper, gets DNS nameserver information)
curl -v https://getgov-<app>.app.cloud.gov/ --resolve 'getgov-<app>.app.cloud.gov:<your-ip-address-from-dig-command-above-here>' (this gets you access to ping to it)
You should be able to play around with your sandbox and see from the curl command above that it’s being pinged. This command is basically log stream, but gives you full access to make sure you can ping the sandbox manually
https://cisa-corp.slack.com/archives/C05BGB4L5NF/p1697810600723069

### Scenario 8: Can’t log into sandbox, permissions do not exist

1. `./manage.py migrate --fake model_name_here file_name_BEFORE_the_most_recent_CREATE_migration` (fake migrate the migration that’s before the last data creation migration -- look for number_create, and then copy the file BEFORE it) 
2. `./manage.py migrate model_name_here file_name_WITH_create` (run the last data creation migration AND ONLY THAT ONE)
3. `./manage.py migrate --fake model_name_here most_recent_file_name` (fake migrate the last migration in the migration list)
4. `./manage.py load` (rerun fixtures)

### Scenario 9: Inconsistent Migration History
If you see `django.db.migrations.exceptions.InconsistentMigrationHistory` error, or when you run `./manage.py showmigrations` it looks like:

[x] 0056_example_migration
[ ] 0057_other_migration
[x] 0058_some_other_migration

1. Go to [database-access.md](../database-access.md#access-certain-table-in-the-database) to see the commands on how to access a certain table in the database.
2. In this case, we want to remove the migration "history" from the `django_migrations` table
3. Once you are in the `cgaws....` table, select the `django_migrations` table with the command `SELECT * FROM django_migrations;`
4. Find the id of the "history" you want to delete. This will be the one in the far left column. For this example, let's pretend the id is 101.
5. Run `DELETE FROM django_migrations WHERE id=101;` where 101 is an example id as seen above.
6. Go to your shell and run `./manage.py showmigrations` to make sure your migrations are now back to the right state. Most likely you will show several unapplied migrations.
7. If you still have unapplied migrations, run `./manage.py migrate`. If an error occurs saying one has already been applied, fake that particular migration `./manage.py migrate --fake model_name_here migration_number` and then run the normal `./manage.py migrate` command to then apply those migrations that come after the one that threw the error.

