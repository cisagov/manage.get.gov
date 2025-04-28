# Adding feature flags
Feature flags are booleans (stored in our DB as the `WaffleFlag` object) that programmatically disable/enable "features" (such as DNS hosting) for a specified set of users.

We use [django-waffle](https://waffle.readthedocs.io/en/stable/) for our feature flags. Waffle makes using flags fairly straight forward.

## Adding feature flags through django admin
1. On the app, navigate to `\admin`.
2. Under models, click `Waffle flags`.
3. Click `Add waffle flag`.
4. Add the model as you would normally. Refer to waffle's documentation [regarding attributes](https://waffle.readthedocs.io/en/stable/types/flag.html#flag-attributes) for more information on them.

### Enabling a feature flag
1. On the app, navigate to `\admin`.
2. Under models, click `Waffle flags`.
3. Click the featue flag record. This should exist by default, if not - create one with that name.
4. (Important) Set the field `Everyone` to `Unknown`. This field overrides all other settings when set to anything else.
5. Configure the settings as you see fit.


## Enabling a feature flag with portfolio permissions
1. Go to file `context_processors.py`
2. Add feature flag name to the `porfolio_context` within the `portfolio_permissions` method. 
3. For the conditional under `if portfolio`, add the feature flag name, and assign the appropiate permission that are in the `user.py` model.

#### Note: 
- If your use case includes non org, you want to add a feature flag outside of it, you can just update the portfolio context outside of the if statement.

## Using feature flags as boolean values
Waffle [provides a boolean](https://waffle.readthedocs.io/en/stable/usage/views.html) called `flag_is_active` that you can use as you otherwise would a boolean. This boolean requires a request object and the flag name.

## Using feature flags to disable/enable views
Waffle [provides a decorator](https://waffle.readthedocs.io/en/stable/usage/decorators.html) that you can use to enable/disable views. When disabled, the view will return a 404 if said user tries to navigate to it.
