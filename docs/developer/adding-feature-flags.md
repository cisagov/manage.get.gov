# Adding feature flags
Feature flags are booleans (stored in our DB as the `WaffleFlag` object) that programmatically disable/enable "features" (such as DNS hosting) for a specified set of users.

We use [django-waffle](https://waffle.readthedocs.io/en/stable/) for our feature flags. Waffle makes using flags fairly straight forward.

## Adding feature flags through django admin
1. On the app, navigate to `\admin`.
2. Under models, click `Waffle flags`.
3. Click `Add waffle flag`.
4. Add the model as you would normally. Refer to waffle's documentation [regarding attributes](https://waffle.readthedocs.io/en/stable/types/flag.html#flag-attributes) for more information on them.

## Adding feature flags when migrations are ran
Given that we store waffle flags as a predefined list, this means that we need to create a new migration file when we want to add a set of feature flags programatically this way. Note that if `WAFFLE_CREATE_MISSING_FLAGS` is set to True, you may not need this step. 

Follow these steps to achieve this:
1. Navigate to `registrar/models/waffle_flag.py`.
2. Modify the `get_default_waffle_flags` and add the desired name of your feature flag to the `default_flags` array.
3. Navigate to `registrar/migrationdata`.
4. Copy the migration named `0091_create_waffle_flags_v01`.
5. Rename the copied migration to match the increment. For instance, if `0091_create_waffle_flags_v01` exists, you will rename your migration to `0091_create_waffle_flags_v02`.
6. Modify the migration dependency to match the last migration in the stack.

## Modifying an existing feature flag through the CLI
Waffle comes with built in management commands that you can use to update records remotely. [Read here](https://waffle.readthedocs.io/en/stable/usage/cli.html) for information on how to use them.

## Using feature flags as boolean values
Waffle [provides a boolean](https://waffle.readthedocs.io/en/stable/usage/views.html) called `flag_is_active` that you can use as you otherwise would a boolean. This boolean requires a request object and the flag name.

## Using feature flags to disable/enable views
Waffle [provides a decorator](https://waffle.readthedocs.io/en/stable/usage/decorators.html) that you can use to enable/disable views. When disabled, the view will return a 404 if said user tries to navigate to it.
